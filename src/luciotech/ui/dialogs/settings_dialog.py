"""Pantalla de Configuración (§5.8): taller, documentos y textos legales.

Aquí se editan **todos** los términos y condiciones y la garantía. Se guardan en la tabla
`configuracion` y los documentos de §13.1 los leen al imprimir, así que un cambio alcanza a
todos los papeles sin tocar el código ni reimprimir con una plantilla vieja.
"""

from __future__ import annotations

from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from luciotech.config import (
    DEFAULT_SERVICE_TERMS,
    DEFAULT_WARRANTY_TERMS,
    MAX_PAGE_MARGIN_MM,
    MIN_PAGE_MARGIN_MM,
    PAPER_SIZES,
)
from luciotech.services.settings_service import (
    budget_validity_days,
    equipment_types,
    page_margin_mm,
    paper_size,
    retention_months,
    service_terms,
    set_budget_validity_days,
    set_equipment_types,
    set_page_margin_mm,
    set_paper_size,
    set_retention_months,
    set_service_terms,
    set_tax_settings,
    set_warranty_days,
    set_warranty_terms,
    set_workshop_details,
    tax_settings,
    warranty_days,
    warranty_terms,
    workshop_address,
    workshop_email,
    workshop_name,
    workshop_phone,
)

ERROR_STYLE = "color: #b00020;"
TAB_TALLER = "Taller"
TAB_DOCUMENTOS = "Documentos"
TAB_LEGAL = "Términos y garantía"


class SettingsDialog(QDialog):
    """Edita la configuración de negocio; solo escribe al pulsar Guardar."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self.setWindowTitle(self.tr("Configuración"))
        self.setMinimumSize(720, 580)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._workshop_tab(), self.tr(TAB_TALLER))
        self._tabs.addTab(self._documents_tab(), self.tr(TAB_DOCUMENTOS))
        self._tabs.addTab(self._legal_tab(), self.tr(TAB_LEGAL))

        self._message = QLabel()
        self._message.setWordWrap(True)
        self._message.setStyleSheet(ERROR_STYLE)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self._save)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addWidget(self._message)
        layout.addWidget(self._buttons)

        self._load()

    def _workshop_tab(self) -> QWidget:
        self._name = QLineEdit()
        self._phone = QLineEdit()
        self._email = QLineEdit()
        self._address = QLineEdit()
        self._tax_percent = QDoubleSpinBox()
        self._tax_percent.setRange(0, 100)
        self._tax_percent.setDecimals(2)
        self._tax_percent.setSuffix(" %")
        self._tax_enabled = QCheckBox(self.tr("IVA activo"))

        form = QFormLayout()
        form.addRow(self.tr("Nombre del taller"), self._name)
        form.addRow(self.tr("Teléfono"), self._phone)
        form.addRow(self.tr("Correo"), self._email)
        form.addRow(self.tr("Dirección"), self._address)
        form.addRow(self.tr("Porcentaje de IVA"), self._tax_percent)
        form.addRow("", self._tax_enabled)

        note = QLabel(
            self.tr(
                "Estos datos salen en la cabecera de todos los documentos. Los precios del "
                "taller ya llevan el impuesto incluido, así que el IVA nace desactivado."
            )
        )
        note.setWordWrap(True)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch(1)
        return _tab(layout)

    def _documents_tab(self) -> QWidget:
        self._paper = QComboBox()
        for name in PAPER_SIZES:
            self._paper.addItem(name, name)
        self._margin = QSpinBox()
        self._margin.setRange(MIN_PAGE_MARGIN_MM, MAX_PAGE_MARGIN_MM)
        self._margin.setSuffix(" mm")
        self._budget_days = QSpinBox()
        self._budget_days.setRange(1, 365)
        self._budget_days.setSuffix(self.tr(" días"))
        self._retention = QSpinBox()
        self._retention.setRange(1, 120)
        self._retention.setSuffix(self.tr(" meses"))
        self._equipment_types = QPlainTextEdit()
        self._equipment_types.setMaximumHeight(110)

        form = QFormLayout()
        form.addRow(self.tr("Tamaño de papel"), self._paper)
        form.addRow(self.tr("Márgenes de la hoja"), self._margin)
        form.addRow(self.tr("Validez del presupuesto"), self._budget_days)
        form.addRow(self.tr("Plazo para retirar un equipo"), self._retention)
        form.addRow(self.tr("Tipos de equipo (uno por línea)"), self._equipment_types)

        note = QLabel(
            self.tr(
                "El plazo de retirada sustituye al marcador {meses} de los términos y "
                "condiciones. Si la lista de tipos se deja vacía, vuelven los valores "
                "por defecto."
            )
        )
        note.setWordWrap(True)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch(1)
        return _tab(layout)

    def _legal_tab(self) -> QWidget:
        self._warranty_days = QSpinBox()
        self._warranty_days.setRange(0, 3650)
        self._warranty_days.setSuffix(self.tr(" días"))

        self._service_terms = QPlainTextEdit()
        self._service_terms.setMinimumHeight(150)
        self._warranty_terms = QPlainTextEdit()
        self._warranty_terms.setMinimumHeight(150)

        self._reset_terms = QPushButton(self.tr("Restablecer texto por defecto"))
        self._reset_terms.clicked.connect(self._restore_service_terms)
        self._reset_warranty = QPushButton(self.tr("Restablecer texto por defecto"))
        self._reset_warranty.clicked.connect(self._restore_warranty_terms)

        days_form = QFormLayout()
        days_form.addRow(self.tr("Garantía de las órdenes nuevas"), self._warranty_days)

        terms_hint = QLabel(
            self.tr(
                "Términos y condiciones: se imprimen en los cuatro documentos que se entregan "
                "al cliente. El marcador {meses} se sustituye por el plazo de Documentos."
            )
        )
        warranty_hint = QLabel(
            self.tr(
                "Condiciones de garantía: mismos documentos, marcadores {dias}, {orden} y "
                "{meses}. Dejar el texto vacío quita el apartado."
            )
        )
        note = QLabel(
            self.tr(
                "Las órdenes ya guardadas conservan sus días de garantía; el texto nuevo sale "
                "en los documentos que se impriman a partir de ahora."
            )
        )
        for label in (terms_hint, warranty_hint, note):
            label.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addLayout(days_form)
        layout.addWidget(terms_hint)
        layout.addLayout(_with_button(self._service_terms, self._reset_terms))
        layout.addWidget(warranty_hint)
        layout.addLayout(_with_button(self._warranty_terms, self._reset_warranty))
        layout.addWidget(note)
        return _tab(layout)

    def _load(self) -> None:
        """Trae a la pantalla lo que hay guardado; lo que falta sale de `config.py`."""
        try:
            with self._session_factory() as session:
                tax = tax_settings(session)
                self._name.setText(workshop_name(session))
                self._phone.setText(workshop_phone(session))
                self._email.setText(workshop_email(session))
                self._address.setText(workshop_address(session))
                self._tax_percent.setValue(float(tax.percent))
                self._tax_enabled.setChecked(tax.enabled)
                index = self._paper.findData(paper_size(session))
                self._paper.setCurrentIndex(max(index, 0))
                self._margin.setValue(page_margin_mm(session))
                self._budget_days.setValue(budget_validity_days(session))
                self._retention.setValue(retention_months(session))
                self._equipment_types.setPlainText("\n".join(equipment_types(session)))
                self._warranty_days.setValue(warranty_days(session))
                self._service_terms.setPlainText(service_terms(session))
                self._warranty_terms.setPlainText(warranty_terms(session))
        except (ValueError, SQLAlchemyError) as exc:
            self._message.setText(
                self.tr("No se pudo leer la configuración: %1").replace("%1", str(exc))
            )

    def _save(self) -> None:
        try:
            with self._session_factory() as session:
                set_workshop_details(
                    session,
                    name=self._name.text(),
                    phone=self._phone.text(),
                    email=self._email.text(),
                    address=self._address.text(),
                )
                set_tax_settings(
                    session,
                    Decimal(str(self._tax_percent.value())),
                    self._tax_enabled.isChecked(),
                )
                set_paper_size(session, self._paper.currentData())
                set_page_margin_mm(session, self._margin.value())
                set_budget_validity_days(session, self._budget_days.value())
                set_retention_months(session, self._retention.value())
                set_equipment_types(session, self._equipment_types.toPlainText())
                set_warranty_days(session, self._warranty_days.value())
                set_service_terms(session, self._service_terms.toPlainText())
                set_warranty_terms(session, self._warranty_terms.toPlainText())
                session.commit()
        except (ValueError, SQLAlchemyError) as exc:
            self._message.setText(
                self.tr("No se pudo guardar la configuración: %1").replace("%1", str(exc))
            )
            return
        self.accept()

    def _restore_service_terms(self) -> None:
        self._service_terms.setPlainText(DEFAULT_SERVICE_TERMS)

    def _restore_warranty_terms(self) -> None:
        self._warranty_terms.setPlainText(DEFAULT_WARRANTY_TERMS)


def _tab(layout: QVBoxLayout) -> QWidget:
    widget = QWidget()
    widget.setLayout(layout)
    return widget


def _with_button(editor: QPlainTextEdit, button: QPushButton) -> QHBoxLayout:
    """El editor de texto legal con su botón de restablecer a la derecha."""
    row = QHBoxLayout()
    row.addWidget(editor, 1)
    row.addWidget(button, 0, Qt.AlignmentFlag.AlignTop)
    return row
