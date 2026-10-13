"""Formulario de recepción: cliente existente o nuevo, equipo, accesorios y fechas (§7)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PyQt6.QtCore import Qt, QDateTime
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from luciotech.database.enums import Priority
from luciotech.database.models import Customer, Equipment
from luciotech.database.repositories import CustomerRepository, EquipmentRepository
from luciotech.services.accessories import build_accessories_text, suggested_accessories
from luciotech.services.customer_service import CustomerData
from luciotech.services.equipment_service import EquipmentData
from luciotech.services.order_number_service import peek_next_order_number
from luciotech.services.reception_service import (
    ReceptionData,
    ReceptionValidationError,
    ReceptionWarnings,
    reception_input_errors,
    reception_warnings,
    register_reception,
)
from luciotech.services.settings_service import equipment_types
from luciotech.ui.validation_texts import error_text, field_label

NEW_CUSTOMER_KEY = -1
NEW_EQUIPMENT_KEY = 0


class ReceptionDialog(QDialog):
    def __init__(self, session_factory: sessionmaker[Session], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self.saved_order_number: str | None = None
        self.saved_order_id: int | None = None
        self.setWindowTitle(self.tr("Nueva recepción"))
        self.setMinimumSize(900, 600)
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

        self._customer_combo = QComboBox()
        self._equipment_combo = QComboBox()
        self._new_name = QLineEdit()
        self._new_identification = QLineEdit()
        self._new_phone = QLineEdit()
        self._new_email = QLineEdit()
        self._new_group = QGroupBox(self.tr("Cliente nuevo"))
        new_form = QFormLayout(self._new_group)
        new_form.addRow(field_label("nombre_completo") + " *", self._new_name)
        new_form.addRow(field_label("numero_identificacion"), self._new_identification)
        new_form.addRow(field_label("telefono_principal"), self._new_phone)
        new_form.addRow(field_label("correo_electronico"), self._new_email)

        self._type = QComboBox()
        self._brand = QLineEdit()
        self._model = QLineEdit()
        self._serial = QLineEdit()
        self._color = QLineEdit()
        self._os = QLineEdit()
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText(self.tr("Opcional"))
        self._problem = QPlainTextEdit()
        self._problem.setFixedHeight(60)
        self._physical_state = QPlainTextEdit()
        self._physical_state.setFixedHeight(50)
        self._intake_notes = QPlainTextEdit()
        self._intake_notes.setFixedHeight(50)
        self._manual_accessories = QLineEdit()
        self._accessory_checks: dict[str, QCheckBox] = {}
        self._accessory_details: dict[str, QLineEdit] = {}
        self._accessories_grid = QGridLayout()
        self._accessories_grid.setColumnStretch(2, 1)

        self._entry = QDateTimeEdit(QDateTime.currentDateTime())
        self._entry.setDisplayFormat("dd/MM/yyyy HH:mm")
        self._estimate = QDateTimeEdit(QDateTime.currentDateTime().addDays(7))
        self._estimate.setDisplayFormat("dd/MM/yyyy HH:mm")
        self._priority = QComboBox()
        self._priority.addItems([p.value for p in Priority])
        self._priority.setCurrentText(Priority.NORMAL.value)
        self._technician = QLineEdit(self.tr("Ing. Lucio"))
        self._diagnosis_cost = QDoubleSpinBox()
        self._diagnosis_cost.setRange(0, 1_000_000)
        self._diagnosis_cost.setDecimals(2)
        self._deposit = QDoubleSpinBox()
        self._deposit.setRange(0, 1_000_000)
        self._deposit.setDecimals(2)

        self._number_label = QLabel()
        self._warning_label = QLabel()
        self._warning_label.setWordWrap(True)
        self._error_label = QLabel()
        self._error_label.setWordWrap(True)

        customer_form = QFormLayout()
        customer_form.addRow(field_label("cliente") + " *", self._customer_combo)
        customer_form.addRow(self.tr("Equipo"), self._equipment_combo)

        equipment_form = QFormLayout()
        equipment_form.addRow(field_label("tipo_equipo") + " *", self._type)
        equipment_form.addRow(self.tr("Marca"), self._brand)
        equipment_form.addRow(self.tr("Modelo"), self._model)
        equipment_form.addRow(self.tr("Número de serie"), self._serial)
        equipment_form.addRow(self.tr("Color"), self._color)
        equipment_form.addRow(self.tr("Sistema operativo"), self._os)
        equipment_form.addRow(self.tr("Contraseña o PIN"), self._password)
        equipment_form.addRow(self.tr("Problema reportado *"), self._problem)
        equipment_form.addRow(self.tr("Estado físico"), self._physical_state)
        equipment_form.addRow(self.tr("Observaciones de ingreso"), self._intake_notes)

        order_form = QFormLayout()
        order_form.addRow(self.tr("Número de orden"), self._number_label)
        order_form.addRow(self.tr("Fecha y hora de ingreso"), self._entry)
        order_form.addRow(self.tr("Fecha estimada de entrega"), self._estimate)
        order_form.addRow(self.tr("Prioridad"), self._priority)
        order_form.addRow(self.tr("Técnico responsable"), self._technician)
        order_form.addRow(self.tr("Costo inicial de diagnóstico"), self._diagnosis_cost)
        order_form.addRow(self.tr("Anticipo recibido"), self._deposit)

        accessories_group = QGroupBox(self.tr("Accesorios recibidos"))
        accessories_layout = QVBoxLayout(accessories_group)
        accessories_layout.addLayout(self._accessories_grid)
        accessories_layout.addWidget(QLabel(self.tr("Otros accesorios:")))
        accessories_layout.addWidget(self._manual_accessories)

        left_column = QVBoxLayout()
        left_column.addWidget(_section(self.tr("Cliente"), customer_form))
        left_column.addWidget(self._new_group)
        left_column.addWidget(_section(self.tr("Equipo"), equipment_form))
        left_column.addStretch(1)

        right_column = QVBoxLayout()
        right_column.addWidget(_section(self.tr("Recepción"), order_form))
        right_column.addWidget(accessories_group)
        right_column.addStretch(1)

        columns = QHBoxLayout()
        columns.addLayout(left_column, 1)
        columns.addLayout(right_column, 1)

        scroll_body = QWidget()
        scroll_body.setLayout(columns)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(scroll_body)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll, 1)
        layout.addWidget(self._warning_label)
        layout.addWidget(self._error_label)
        layout.addWidget(buttons)

        self._customer_combo.currentIndexChanged.connect(self._on_customer_changed)
        self._equipment_combo.currentIndexChanged.connect(lambda _index: self._on_equipment_changed())
        self._type.currentTextChanged.connect(self._rebuild_accessories)
        self._entry.dateTimeChanged.connect(self._refresh_number)
        self._load_choices()
        self._refresh_number()

    # Carga inicial

    def _load_choices(self) -> None:
        with self._session_factory() as session:
            self._customer_combo.addItem(self.tr("— Cliente nuevo —"), NEW_CUSTOMER_KEY)
            for customer in CustomerRepository(session).list_all():
                self._customer_combo.addItem(customer.nombre_completo, customer.id)
            self._type.addItems(equipment_types(session))
        self._rebuild_accessories(self._type.currentText())
        self._on_customer_changed()

    def _rebuild_accessories(self, tipo: str) -> None:
        while self._accessories_grid.count():
            item = self._accessories_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._accessory_checks = {}
        self._accessory_details = {}
        for row, name in enumerate(suggested_accessories(tipo)):
            check = QCheckBox(name)
            detail = QLineEdit()
            detail.setPlaceholderText(self.tr("Modelo o detalle"))
            detail.setEnabled(False)
            check.toggled.connect(detail.setEnabled)
            self._accessory_checks[name] = check
            self._accessory_details[name] = detail
            self._accessories_grid.addWidget(check, row, 0)
            self._accessories_grid.addWidget(detail, row, 1, 1, 2)

    def _on_customer_changed(self) -> None:
        is_new = self._customer_combo.currentData() == NEW_CUSTOMER_KEY
        self._new_group.setVisible(is_new)
        self._reload_equipment_choices()

    def _reload_equipment_choices(self) -> None:
        self._equipment_combo.blockSignals(True)
        self._equipment_combo.clear()
        self._equipment_combo.addItem(self.tr("— Equipo nuevo —"), NEW_EQUIPMENT_KEY)
        customer_id = self._customer_combo.currentData()
        if customer_id is not None and customer_id != NEW_CUSTOMER_KEY:
            with self._session_factory() as session:
                for equipment in EquipmentRepository(session).list_all():
                    if equipment.cliente_id == int(customer_id):
                        label = " ".join(
                            part for part in (equipment.tipo_equipo, equipment.marca, equipment.modelo) if part
                        )
                        self._equipment_combo.addItem(label, equipment.id)
        self._equipment_combo.blockSignals(False)
        self._equipment_combo.setCurrentIndex(0)
        self._on_equipment_changed()

    def _on_equipment_changed(self) -> None:
        existing_id = self._equipment_combo.currentData()
        reuse = existing_id is not None and existing_id != NEW_EQUIPMENT_KEY
        for field in (self._type, self._brand, self._model, self._serial, self._color, self._os, self._password):
            field.setEnabled(not reuse)
        if reuse:
            self._fill_from_equipment(int(existing_id))

    def _fill_from_equipment(self, equipment_id: int) -> None:
        with self._session_factory() as session:
            equipment = session.get(Equipment, equipment_id)
            if equipment is None:
                return
            self._select_or_add_type(equipment.tipo_equipo)
            self._brand.setText(equipment.marca or "")
            self._model.setText(equipment.modelo or "")
            self._serial.setText(equipment.numero_serie or "")
            self._color.setText(equipment.color or "")
            self._os.setText(equipment.sistema_operativo or "")
            self._password.setText(equipment.contrasena_equipo or "")

    def _select_or_add_type(self, tipo: str) -> None:
        index = self._type.findText(tipo)
        if index < 0:
            self._type.addItem(tipo)
            index = self._type.count() - 1
        self._type.setCurrentIndex(index)

    def _refresh_number(self) -> None:
        year = self._entry.dateTime().toPyDateTime().year
        with self._session_factory() as session:
            self._number_label.setText(peek_next_order_number(session, year))

    # Datos del formulario

    def _collect(self) -> ReceptionData:
        is_new = self._customer_combo.currentData() == NEW_CUSTOMER_KEY
        customer_id = None if is_new else self._customer_combo.currentData()
        new_customer = (
            CustomerData(
                nombre_completo=self._new_name.text(),
                numero_identificacion=self._new_identification.text(),
                telefono_principal=self._new_phone.text(),
                correo_electronico=self._new_email.text(),
            )
            if is_new
            else None
        )
        selected = [name for name, check in self._accessory_checks.items() if check.isChecked()]
        details = {name: self._accessory_details[name].text() for name in selected}
        equipment = EquipmentData(
            cliente_id=None,
            tipo_equipo=self._type.currentText(),
            marca=self._brand.text(),
            modelo=self._model.text(),
            numero_serie=self._serial.text(),
            color=self._color.text(),
            sistema_operativo=self._os.text(),
            contrasena_equipo=self._password.text(),
            accesorios_recibidos=build_accessories_text(
                selected, self._manual_accessories.text(), details
            ),
            estado_fisico=self._physical_state.toPlainText(),
            problema_reportado_cliente=self._problem.toPlainText(),
            observaciones_ingreso=self._intake_notes.toPlainText(),
        )
        chosen_equipment = self._equipment_combo.currentData()
        reuse_id = (
            int(chosen_equipment)
            if chosen_equipment is not None and chosen_equipment != NEW_EQUIPMENT_KEY
            else None
        )
        return ReceptionData(
            equipment=equipment,
            customer_id=int(customer_id) if customer_id is not None else None,
            new_customer=new_customer,
            equipment_id=reuse_id,
            fecha_ingreso=self._entry.dateTime().toPyDateTime(),
            fecha_estimada_entrega=self._estimate.dateTime().toPyDateTime(),
            prioridad=self._priority.currentText(),
            tecnico_responsable=self._technician.text().strip() or None,
            costo_diagnostico=_decimal(self._diagnosis_cost.value()),
            anticipo=_decimal(self._deposit.value()),
        )

    def _save(self) -> None:
        data = self._collect()
        try:
            with self._session_factory() as session:
                errors = reception_input_errors(session, data)
                if errors:
                    self._show_errors(errors)
                    return
                warnings = reception_warnings(session, data)
                if warnings.has_any and not self._confirm_warnings(warnings):
                    return
                order = register_reception(session, data)
                session.commit()
                self.saved_order_number = order.numero_orden
                self.saved_order_id = order.id
        except ReceptionValidationError as exc:
            self._show_errors(exc.errors)
            return
        except SQLAlchemyError:
            QMessageBox.critical(
                self,
                self.windowTitle(),
                self.tr("No se pudo registrar la recepción. Intente de nuevo."),
            )
            return
        self.accept()

    def _confirm_warnings(self, warnings: ReceptionWarnings) -> bool:
        lines: list[str] = []
        for customer in warnings.duplicate_customers:
            lines.append(self.tr("Cliente parecido: %1").replace("%1", _customer_label(customer)))
        for order in warnings.serial_orders:
            lines.append(self.tr("Mismo número de serie en la orden %1").replace("%1", order.numero_orden))
        message = "\n".join(lines) + "\n\n" + self.tr("¿Desea registrar la recepción de todos modos?")
        answer = QMessageBox.question(
            self,
            self.windowTitle(),
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _show_errors(self, errors: dict[str, str]) -> None:
        self._error_label.setText(
            "\n".join(f"{field_label(field)}: {error_text(code)}" for field, code in errors.items())
        )


def _decimal(value: float) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0.00")


def _customer_label(customer: Customer) -> str:
    return f"{customer.nombre_completo} ({customer.telefono_principal or '-'})"


def _section(title: str, content: QFormLayout) -> QGroupBox:
    box = QGroupBox(title)
    box.setLayout(content)
    return box
