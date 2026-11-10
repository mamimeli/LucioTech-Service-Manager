"""Pruebas de la pantalla de Configuración (§5.8)."""

from __future__ import annotations

from decimal import Decimal

from PyQt6.QtWidgets import QDialog, QLabel
from pytestqt.qtbot import QtBot
from sqlalchemy.orm import Session, sessionmaker

from luciotech.config import (
    DEFAULT_SERVICE_TERMS,
    DEFAULT_WARRANTY_DAYS,
    DEFAULT_WARRANTY_TERMS,
)
from luciotech.database.enums import UserRole
from luciotech.services import settings_service as settings
from luciotech.services.user_service import CurrentUser
from luciotech.ui.dialogs.settings_dialog import (
    TAB_DOCUMENTOS,
    TAB_LEGAL,
    TAB_TALLER,
    SettingsDialog,
)
from luciotech.ui.main_window import MainWindow


def _dialog(qtbot: QtBot, session_factory: sessionmaker[Session]) -> SettingsDialog:
    dialog = SettingsDialog(session_factory)
    qtbot.addWidget(dialog)
    return dialog


def _titles(window: MainWindow) -> list[str]:
    menu = window.menuBar().actions()[0].menu()
    return [action.text() for action in menu.actions()]


def test_settings_dialog_has_the_three_tabs_with_the_default_legal_texts(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    dialog = _dialog(qtbot, session_factory)

    assert [
        dialog._tabs.tabText(index) for index in range(dialog._tabs.count())
    ] == [TAB_TALLER, TAB_DOCUMENTOS, TAB_LEGAL]
    assert dialog._service_terms.toPlainText() == DEFAULT_SERVICE_TERMS
    assert dialog._warranty_terms.toPlainText() == DEFAULT_WARRANTY_TERMS
    assert dialog._warranty_days.value() == DEFAULT_WARRANTY_DAYS


def test_settings_dialog_explains_every_placeholder(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    dialog = _dialog(qtbot, session_factory)
    labels = [label.text() for label in dialog.findChildren(QLabel)]

    assert any("{meses}" in text for text in labels)
    assert any("{dias}" in text and "{orden}" in text for text in labels)


def test_settings_dialog_loads_the_saved_configuration(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        settings.set_workshop_details(
            session,
            name="Taller Central",
            phone="0991234567",
            email="taller@ejemplo.com",
            address="Av. 1",
        )
        settings.set_tax_settings(session, Decimal("12"), True)
        settings.set_paper_size(session, "Carta")
        settings.set_page_margin_mm(session, 20)
        settings.set_budget_validity_days(session, 30)
        settings.set_retention_months(session, 9)
        settings.set_equipment_types(session, "Laptop\nImpresora")
        settings.set_warranty_days(session, 90)
        settings.set_service_terms(session, "Condiciones propias")
        settings.set_warranty_terms(session, "Garantía propia")
        session.commit()

    dialog = _dialog(qtbot, session_factory)

    assert dialog._name.text() == "Taller Central"
    assert dialog._phone.text() == "0991234567"
    assert dialog._email.text() == "taller@ejemplo.com"
    assert dialog._address.text() == "Av. 1"
    assert dialog._tax_percent.value() == 12.0
    assert dialog._tax_enabled.isChecked()
    assert dialog._paper.currentData() == "Carta"
    assert dialog._margin.value() == 20
    assert dialog._budget_days.value() == 30
    assert dialog._retention.value() == 9
    assert dialog._equipment_types.toPlainText() == "Laptop\nImpresora"
    assert dialog._warranty_days.value() == 90
    assert dialog._service_terms.toPlainText() == "Condiciones propias"
    assert dialog._warranty_terms.toPlainText() == "Garantía propia"


def test_settings_dialog_saves_every_tab(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    dialog = _dialog(qtbot, session_factory)
    dialog._name.setText("Taller del Sur")
    dialog._phone.setText("0987654321")
    dialog._email.setText("sur@ejemplo.com")
    dialog._address.setText("Calle 2")
    dialog._tax_percent.setValue(12.0)
    dialog._tax_enabled.setChecked(True)
    dialog._paper.setCurrentIndex(dialog._paper.findData("Carta"))
    dialog._margin.setValue(25)
    dialog._budget_days.setValue(45)
    dialog._retention.setValue(10)
    dialog._equipment_types.setPlainText("Laptop\nTablet")
    dialog._warranty_days.setValue(120)
    dialog._service_terms.setPlainText("Nuevas condiciones con {meses} meses.")
    dialog._warranty_terms.setPlainText("Garantía de {dias} días.")

    dialog._save()

    assert dialog.result() == QDialog.DialogCode.Accepted
    with session_factory() as session:
        assert settings.workshop_name(session) == "Taller del Sur"
        assert settings.workshop_contact(session) == "0987654321 · sur@ejemplo.com · Calle 2"
        assert settings.tax_settings(session).percent == Decimal("12")
        assert settings.tax_settings(session).enabled
        assert settings.paper_size(session) == "Carta"
        assert settings.page_margin_mm(session) == 25
        assert settings.budget_validity_days(session) == 45
        assert settings.retention_months(session) == 10
        assert settings.equipment_types(session) == ["Laptop", "Tablet"]
        assert settings.warranty_days(session) == 120
        assert settings.service_terms(session) == "Nuevas condiciones con {meses} meses."
        assert settings.warranty_terms(session) == "Garantía de {dias} días."


def test_cancel_does_not_touch_the_database(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    dialog = _dialog(qtbot, session_factory)
    dialog._service_terms.setPlainText("Texto que no se guarda")

    dialog.reject()

    with session_factory() as session:
        assert settings.service_terms(session) == DEFAULT_SERVICE_TERMS


def test_restore_buttons_put_back_the_default_legal_texts(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    dialog = _dialog(qtbot, session_factory)
    dialog._service_terms.setPlainText("Otro texto")
    dialog._warranty_terms.setPlainText("Otra garantía")

    dialog._reset_terms.click()
    dialog._reset_warranty.click()

    assert dialog._service_terms.toPlainText() == DEFAULT_SERVICE_TERMS
    assert dialog._warranty_terms.toPlainText() == DEFAULT_WARRANTY_TERMS


def test_a_blank_warranty_text_can_be_saved(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    dialog = _dialog(qtbot, session_factory)
    dialog._warranty_terms.setPlainText("   ")

    dialog._save()

    with session_factory() as session:
        assert settings.warranty_terms(session) == ""


def test_only_an_administrator_sees_the_settings_menu(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    admin = CurrentUser(
        id=1, username="ana", full_name="Ana", role=UserRole.ADMINISTRADOR.value
    )
    technician = CurrentUser(
        id=2, username="luis", full_name="Luis", role=UserRole.TECNICO.value
    )
    admin_window = MainWindow(session_factory, admin)
    technician_window = MainWindow(session_factory, technician)
    qtbot.addWidget(admin_window)
    qtbot.addWidget(technician_window)

    assert "&Configuración…" in _titles(admin_window)
    assert "&Configuración…" not in _titles(technician_window)
