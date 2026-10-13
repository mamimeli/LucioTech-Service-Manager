"""Pestaña «Presupuesto y pagos» de una orden (§9, §12 y §5.7).

Líneas de presupuesto con alta, edición y baja, descuento editable, totales recalculados en vivo
y listado de pagos con registro y anulación. Todo pasa por los servicios: la pestaña no escribe
SQL ni calcula importes por su cuenta.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from luciotech.database.enums import BudgetLineType, PaymentMethod, PaymentType
from luciotech.database.models import BudgetLine, Payment, ServiceOrder
from luciotech.services.budget_service import (
    BudgetLineValidationError,
    add_line,
    line_subtotal,
    lines_for_order,
    remove_line,
    set_discount,
    update_line,
)
from luciotech.services.order_detail_service import (
    PaymentValidationError,
    deposit_warning,
    payments_for_order,
    register_payment,
    void_payment,
)
from luciotech.services.settings_service import TaxSettings, tax_settings
from luciotech.services.totals_service import order_totals
from luciotech.ui.formatting import format_datetime, format_money
from luciotech.ui.validation_texts import error_text

CENT = Decimal("0.01")
ZERO = Decimal("0.00")

LINE_COLUMNS = ("Tipo", "Descripción", "Cantidad", "Precio unitario", "Subtotal")
PAYMENT_COLUMNS = ("Fecha", "Tipo", "Método", "Importe", "Referencia", "Estado")


class BudgetLineDialog(QDialog):
    """Alta y edición de una línea de presupuesto (§12)."""

    def __init__(self, parent: QWidget | None = None, line: BudgetLine | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Línea de presupuesto"))
        self._type = QComboBox()
        for kind in BudgetLineType:
            self._type.addItem(kind.value, kind.value)
        self._description = QLineEdit()
        self._quantity = QLineEdit("1")
        self._price = QLineEdit("0.00")

        form = QFormLayout(self)
        form.addRow(self.tr("Tipo"), self._type)
        form.addRow(self.tr("Descripción"), self._description)
        form.addRow(self.tr("Cantidad"), self._quantity)
        form.addRow(self.tr("Precio unitario"), self._price)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        if line is not None:
            index = self._type.findData(line.tipo_linea)
            if index >= 0:
                self._type.setCurrentIndex(index)
            self._description.setText(line.descripcion)
            self._quantity.setText(_plain(line.cantidad))
            self._price.setText(_plain(line.precio_unitario))

    def values(self) -> tuple[str, str, Decimal, Decimal] | None:
        """Devuelve los datos del formulario, o None si cantidad o precio no son números."""
        quantity = _parse(self._quantity.text())
        price = _parse(self._price.text())
        if quantity is None or price is None:
            return None
        return (self._type.currentData(), self._description.text(), quantity, price)


class PaymentDialog(QDialog):
    """Registro de un pago o reembolso (§5.7)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Registrar pago"))
        self._type = QComboBox()
        for kind in PaymentType:
            self._type.addItem(kind.value, kind.value)
        self._method = QComboBox()
        for method in PaymentMethod:
            self._method.addItem(method.value, method.value)
        self._amount = QLineEdit("0.00")
        self._reference = QLineEdit()
        self._observations = QLineEdit()

        form = QFormLayout(self)
        form.addRow(self.tr("Tipo"), self._type)
        form.addRow(self.tr("Método"), self._method)
        form.addRow(self.tr("Importe"), self._amount)
        form.addRow(self.tr("Referencia"), self._reference)
        form.addRow(self.tr("Observaciones"), self._observations)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> tuple[str, str, Decimal, str, str] | None:
        """Devuelve los datos del formulario, o None si el importe no es un número."""
        amount = _parse(self._amount.text())
        if amount is None:
            return None
        return (
            self._type.currentData(),
            self._method.currentData(),
            amount,
            self._reference.text(),
            self._observations.text(),
        )


class BudgetPaymentsTab(QWidget):
    """Presupuesto detallado, descuento, totales en vivo y pagos de una orden."""

    changed = pyqtSignal()

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        usuario: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._usuario = usuario
        self._order_id: int | None = None

        self._lines = _table(LINE_COLUMNS)
        self._lines.itemDoubleClicked.connect(lambda _item: self._edit_line())
        add_button = QPushButton(self.tr("Añadir línea"))
        add_button.clicked.connect(self._add_line)
        edit_button = QPushButton(self.tr("Editar línea"))
        edit_button.clicked.connect(self._edit_line)
        remove_button = QPushButton(self.tr("Quitar línea"))
        remove_button.clicked.connect(self._remove_line)

        budget_box = QGroupBox(self.tr("Presupuesto"))
        budget_layout = QVBoxLayout(budget_box)
        budget_layout.addWidget(self._lines)
        budget_buttons = QHBoxLayout()
        budget_buttons.addWidget(add_button)
        budget_buttons.addWidget(edit_button)
        budget_buttons.addWidget(remove_button)
        budget_buttons.addStretch(1)
        budget_layout.addLayout(budget_buttons)

        self._discount = QLineEdit()
        self._discount.setPlaceholderText("0.00")
        self._discount.editingFinished.connect(self._apply_discount)

        self._totals_labels: dict[str, QLabel] = {}
        self._totals_values: dict[str, QLabel] = {}
        totals_box = QGroupBox(self.tr("Totales"))
        totals_form = QFormLayout(totals_box)
        self._add_total_row(totals_form, "subtotal", self.tr("Subtotal"))
        totals_form.addRow(self.tr("Descuento"), self._discount)
        self._add_total_row(totals_form, "iva", self.tr("IVA"))
        self._add_total_row(totals_form, "total", self.tr("Total"))
        self._add_total_row(totals_form, "anticipo", self.tr("Anticipo (recepción)"))
        self._add_total_row(totals_form, "pagos", self.tr("Pagos recibidos"))
        self._add_total_row(totals_form, "saldo", self.tr("Saldo pendiente"))

        self._payments = _table(PAYMENT_COLUMNS)
        pay_button = QPushButton(self.tr("Registrar pago"))
        pay_button.clicked.connect(self._register_payment)
        void_button = QPushButton(self.tr("Anular pago"))
        void_button.clicked.connect(self._void_payment)

        payments_box = QGroupBox(self.tr("Pagos"))
        payments_layout = QVBoxLayout(payments_box)
        payments_layout.addWidget(self._payments)
        payment_buttons = QHBoxLayout()
        payment_buttons.addWidget(pay_button)
        payment_buttons.addWidget(void_button)
        payment_buttons.addStretch(1)
        payments_layout.addLayout(payment_buttons)

        self._message = QLabel()
        self._message.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(budget_box, 3)
        layout.addWidget(totals_box)
        layout.addWidget(payments_box, 2)
        layout.addWidget(self._message)

    def set_order(self, order_id: int | None) -> None:
        self._message.clear()
        self._order_id = order_id
        self.refresh()

    def refresh(self) -> None:
        """Vuelve a leer el presupuesto y los pagos desde la base de datos."""
        if self._order_id is None:
            return
        with self._session_factory() as session:
            order = session.get(ServiceOrder, self._order_id)
            if order is None:
                self._message.setText(self.tr("La orden ya no existe."))
                return
            tax = tax_settings(session)
            self._fill_lines(lines_for_order(session, self._order_id))
            self._fill_payments(payments_for_order(order))
            self._show_totals(order, tax)

    def _add_total_row(self, form: QFormLayout, key: str, text: str) -> None:
        label = QLabel(text)
        value = QLabel()
        self._totals_labels[key] = label
        self._totals_values[key] = value
        form.addRow(label, value)

    def _fill_lines(self, lines: list[BudgetLine]) -> None:
        self._lines.setRowCount(len(lines))
        for row, line in enumerate(lines):
            cells = (
                line.tipo_linea,
                line.descripcion,
                _plain(line.cantidad),
                _plain(line.precio_unitario),
                format_money(line_subtotal(line)),
            )
            for column, value in enumerate(cells):
                self._lines.setItem(row, column, QTableWidgetItem(value))

    def _fill_payments(self, payments: list[Payment]) -> None:
        self._payments.setRowCount(len(payments))
        for row, payment in enumerate(payments):
            cells = (
                format_datetime(payment.fecha),
                payment.tipo_pago,
                payment.metodo_pago,
                format_money(payment.monto),
                payment.referencia or "-",
                self.tr("Anulado") if payment.anulado else self.tr("Vigente"),
            )
            for column, value in enumerate(cells):
                self._payments.setItem(row, column, QTableWidgetItem(value))

    def _show_totals(self, order: ServiceOrder, tax: TaxSettings) -> None:
        totals = order_totals(order, tax)
        self._totals_labels["iva"].setText(
            (self.tr("IVA") + f" ({tax.percent}%)") if tax.enabled else self.tr("IVA (desactivado)")
        )
        self._totals_values["subtotal"].setText(format_money(totals.subtotal))
        self._totals_values["iva"].setText(format_money(totals.impuestos))
        self._totals_values["total"].setText(format_money(totals.total))
        self._totals_values["anticipo"].setText(format_money(order.anticipo))
        self._totals_values["pagos"].setText(format_money(totals.pagos_realizados))
        self._totals_values["saldo"].setText(format_money(totals.saldo_pendiente))
        if not self._discount.hasFocus():
            self._discount.setText(_plain(order.descuento))

    def _selected_line(self) -> BudgetLine | None:
        row = self._lines.currentRow()
        if row < 0 or self._order_id is None:
            return None
        with self._session_factory() as session:
            lines = lines_for_order(session, self._order_id)
        return lines[row] if row < len(lines) else None

    def _selected_payment(self) -> Payment | None:
        row = self._payments.currentRow()
        if row < 0 or self._order_id is None:
            return None
        with self._session_factory() as session:
            order = session.get(ServiceOrder, self._order_id)
            if order is None:
                return None
            payments = payments_for_order(order)
        return payments[row] if row < len(payments) else None

    def _add_line(self) -> None:
        self._message.clear()
        dialog = BudgetLineDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if values is None:
            self._message.setText(error_text("amount.invalid"))
            return
        tipo, descripcion, cantidad, precio = values
        self._run(
            lambda session, order: add_line(
                session, order, tipo=tipo, descripcion=descripcion,
                cantidad=cantidad, precio_unitario=precio,
            )
        )

    def _edit_line(self) -> None:
        self._message.clear()
        line = self._selected_line()
        if line is None:
            self._message.setText(self.tr("Seleccione una línea."))
            return
        dialog = BudgetLineDialog(self, line)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if values is None:
            self._message.setText(error_text("amount.invalid"))
            return
        tipo, descripcion, cantidad, precio = values
        self._run(
            lambda session, order: update_line(
                session, _line_of(session, line.id), tipo=tipo, descripcion=descripcion,
                cantidad=cantidad, precio_unitario=precio,
            )
        )

    def _remove_line(self) -> None:
        self._message.clear()
        line = self._selected_line()
        if line is None:
            self._message.setText(self.tr("Seleccione una línea."))
            return
        self._run(lambda session, order: remove_line(session, _line_of(session, line.id)))

    def _apply_discount(self) -> None:
        self._message.clear()
        if self._order_id is None:
            return
        value = _parse(self._discount.text())
        if value is None:
            self.refresh()
            self._message.setText(error_text("amount.invalid"))
            return
        self._run(lambda session, order: set_discount(session, order, value))

    def _register_payment(self) -> None:
        self._message.clear()
        dialog = PaymentDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if values is None:
            self._message.setText(error_text("amount.invalid"))
            return
        tipo, metodo, monto, referencia, observaciones = values
        warning = self._deposit_warning(tipo)
        if self._run(
            lambda session, order: register_payment(
                session, order, tipo=tipo, metodo=metodo, monto=monto, usuario=self._usuario,
                referencia=referencia, observaciones=observaciones,
            )
        ) and warning is not None:
            self._message.setText(error_text(warning))

    def _deposit_warning(self, tipo: str) -> str | None:
        if self._order_id is None:
            return None
        with self._session_factory() as session:
            order = session.get(ServiceOrder, self._order_id)
            return None if order is None else deposit_warning(order, tipo)

    def _void_payment(self) -> None:
        self._message.clear()
        payment = self._selected_payment()
        if payment is None:
            self._message.setText(self.tr("Seleccione un pago."))
            return
        motivo, accepted = QInputDialog.getText(
            self,
            self.tr("Anular pago"),
            self.tr("Motivo de la anulación (opcional):"),
        )
        if not accepted:
            return
        self._run(
            lambda session, order: void_payment(
                session, order, _payment_of(session, payment.id),
                usuario=self._usuario, motivo=motivo,
            )
        )

    def _run(self, action: Callable[[Session, ServiceOrder], object]) -> bool:
        """Ejecuta una acción dentro de una sesión, la confirma y refresca la vista."""
        if self._order_id is None:
            return False
        try:
            with self._session_factory() as session:
                order = session.get(ServiceOrder, self._order_id)
                if order is None:
                    raise ValueError(self.tr("La orden ya no existe."))
                action(session, order)
                session.commit()
        except (BudgetLineValidationError, PaymentValidationError) as exc:
            self._message.setText("\n".join(error_text(code) for code in exc.errors.values()))
            return False
        except ValueError as exc:
            self._message.setText(str(exc))
            return False
        except SQLAlchemyError:
            QMessageBox.critical(
                self, self.windowTitle(), self.tr("No se pudo guardar. Intente de nuevo.")
            )
            return False
        self.refresh()
        self._message.setText(self.tr("Guardado."))
        self.changed.emit()
        return True


def _table(columns: tuple[str, ...]) -> QTableWidget:
    table = QTableWidget(0, len(columns))
    table.setHorizontalHeaderLabels(list(columns))
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    return table


def _line_of(session: Session, line_id: int) -> BudgetLine:
    line = session.get(BudgetLine, line_id)
    if line is None:
        raise ValueError("La línea ya no existe.")
    return line


def _payment_of(session: Session, payment_id: int) -> Payment:
    payment = session.get(Payment, payment_id)
    if payment is None:
        raise ValueError("El pago ya no existe.")
    return payment


def _plain(value: Decimal | None) -> str:
    return f"{value if value is not None else ZERO:.2f}"


def _parse(text: str) -> Decimal | None:
    try:
        return Decimal(text.strip().replace(",", ".")).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None
