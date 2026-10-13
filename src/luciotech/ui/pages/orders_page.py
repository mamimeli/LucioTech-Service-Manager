"""Lista de órdenes con filtros básicos y acceso a nueva recepción (§10, alcance Fase 1)."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
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

from luciotech.database.enums import OrderState, Priority
from luciotech.database.models import ServiceOrder
from luciotech.services.order_query_service import OrderFilter, search_orders
from luciotech.services.order_service import soft_delete_order
from luciotech.services.settings_service import equipment_types
from luciotech.ui.dialogs.order_detail_dialog import OrderDetailDialog
from luciotech.ui.dialogs.reception_dialog import ReceptionDialog
from luciotech.ui.documents import print_order_receipt
from luciotech.ui.formatting import format_datetime, format_money

OPERATOR = "Ing. Lucio"

ANY = ""
COLUMNS = (
    "Número de orden",
    "Fecha de ingreso",
    "Cliente",
    "Tipo de equipo",
    "Marca y modelo",
    "Estado",
    "Prioridad",
    "Total",
    "Saldo",
)


class OrdersPage(QWidget):
    data_changed = pyqtSignal()

    def __init__(self, session_factory: sessionmaker[Session], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory

        self._text = QLineEdit()
        self._text.setPlaceholderText(self.tr("Número, cliente, teléfono, serie, marca o modelo"))
        self._text.setClearButtonEnabled(True)
        self._state = QComboBox()
        self._priority = QComboBox()
        self._equipment_type = QComboBox()
        self._only_balance = QCheckBox(self.tr("Con saldo pendiente"))
        self._new_button = QPushButton(self.tr("Nueva recepción"))
        self._new_button.clicked.connect(self._new_reception)
        self._delete_button = QPushButton(self.tr("Eliminar"))
        self._delete_button.setToolTip(self.tr("Envía la orden seleccionada a la papelera"))
        self._delete_button.clicked.connect(self._delete_selected)
        self._order_ids: list[int] = []

        self._state.addItem(self.tr("Todos los estados"), ANY)
        for state in OrderState:
            self._state.addItem(state.value, state.value)
        self._priority.addItem(self.tr("Todas las prioridades"), ANY)
        for priority in Priority:
            self._priority.addItem(priority.value, priority.value)

        filters = QHBoxLayout()
        filters.addWidget(self._text, 2)
        filters.addWidget(self._state)
        filters.addWidget(self._priority)
        filters.addWidget(self._equipment_type)
        filters.addWidget(self._only_balance)
        filters.addWidget(self._new_button)
        filters.addWidget(self._delete_button)

        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setHorizontalHeaderLabels([self.tr(c) for c in COLUMNS])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSortingEnabled(False)
        self._table.doubleClicked.connect(lambda _index: self.open_selected())

        self._text.textChanged.connect(lambda _text: self.refresh())
        self._state.currentIndexChanged.connect(lambda _index: self.refresh())
        self._priority.currentIndexChanged.connect(lambda _index: self.refresh())
        self._equipment_type.currentIndexChanged.connect(lambda _index: self.refresh())
        self._only_balance.toggled.connect(lambda _checked: self.refresh())

        layout = QVBoxLayout(self)
        layout.addLayout(filters)
        layout.addWidget(self._table)
        self._load_equipment_types()
        self.refresh()

    def _load_equipment_types(self) -> None:
        with self._session_factory() as session:
            types = equipment_types(session)
        self._equipment_type.clear()
        self._equipment_type.addItem(self.tr("Todos los tipos"), ANY)
        for tipo in types:
            self._equipment_type.addItem(tipo, tipo)

    def current_filter(self) -> OrderFilter:
        return OrderFilter(
            text=self._text.text(),
            estado=self._state.currentData() or None,
            prioridad=self._priority.currentData() or None,
            tipo_equipo=self._equipment_type.currentData() or None,
            solo_con_saldo=self._only_balance.isChecked(),
        )

    def refresh(self) -> None:
        with self._session_factory() as session:
            orders = search_orders(session, self.current_filter())
            self._order_ids = [order.id for order in orders]
            rows = [
                [
                    order.numero_orden,
                    format_datetime(order.fecha_ingreso),
                    order.customer.nombre_completo,
                    order.equipment.tipo_equipo,
                    " ".join(part for part in (order.equipment.marca, order.equipment.modelo) if part),
                    order.estado,
                    order.prioridad,
                    format_money(order.total),
                    format_money(order.saldo_pendiente),
                ]
                for order in orders
            ]
        self._table.setRowCount(len(rows))
        for row, cells in enumerate(rows):
            for column, value in enumerate(cells):
                self._table.setItem(row, column, QTableWidgetItem(value))
        self._table.resizeColumnsToContents()

    def visible_row_count(self) -> int:
        return self._table.rowCount()

    def order_number_at(self, row: int) -> str:
        item = self._table.item(row, 0)
        return item.text() if item is not None else ""

    def open_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        self.open_order(self._order_ids[row])

    def open_order(self, order_id: int) -> None:
        dialog = OrderDetailDialog(self._session_factory, order_id, OPERATOR, parent=self)
        dialog.exec()
        self.refresh()
        self.data_changed.emit()

    def _delete_selected(self) -> None:
        """Borra lógicamente la orden seleccionada, con confirmación previa (§18)."""
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.information(
                self, self.windowTitle(), self.tr("Seleccione una orden de la lista.")
            )
            return
        number = self.order_number_at(row)
        answer = QMessageBox.warning(
            self,
            self.windowTitle(),
            self.tr(
                "La orden %1 se enviará a la papelera y dejará de aparecer en la lista. "
                "Podrá restaurarla desde la pestaña Papelera.\n\n¿Desea continuar?"
            ).replace("%1", number),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        order_id = self._order_ids[row]
        try:
            with self._session_factory() as session:
                order = session.get(ServiceOrder, order_id)
                if order is None:
                    raise ValueError(self.tr("La orden ya no existe."))
                soft_delete_order(session, order, usuario=OPERATOR)
                session.commit()
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        except SQLAlchemyError:
            QMessageBox.critical(
                self, self.windowTitle(), self.tr("No se pudo eliminar. Intente de nuevo.")
            )
            return
        self.refresh()
        self.data_changed.emit()

    def _new_reception(self) -> None:
        dialog = ReceptionDialog(self._session_factory, parent=self)
        if not dialog.exec():
            return
        self.refresh()
        self.data_changed.emit()
        if dialog.saved_order_id is not None:
            self._offer_follow_up(dialog.saved_order_id, dialog.saved_order_number or "")

    def _offer_follow_up(self, order_id: int, numero_orden: str) -> None:
        """Tras guardar la recepción se ofrece abrir la orden o imprimir el comprobante (§7.5)."""
        box = QMessageBox(self)
        box.setWindowTitle(self.tr("Recepción registrada"))
        box.setText(
            self.tr("La recepción quedó registrada con el número %1.").replace("%1", numero_orden)
        )
        print_button = box.addButton(
            self.tr("Imprimir comprobante"), QMessageBox.ButtonRole.AcceptRole
        )
        open_button = box.addButton(self.tr("Abrir orden"), QMessageBox.ButtonRole.ActionRole)
        box.addButton(self.tr("Cerrar"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is print_button:
            print_order_receipt(self._session_factory, order_id, self)
        elif clicked is open_button:
            self.open_order(order_id)
