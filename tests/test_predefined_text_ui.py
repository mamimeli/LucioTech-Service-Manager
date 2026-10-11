"""Pruebas de UI de los textos predefinidos en el editor y en el detalle de orden."""

from __future__ import annotations

from datetime import datetime

import pytest
from pytestqt.qtbot import QtBot
from sqlalchemy.orm import Session, sessionmaker

from luciotech.config import DEFAULT_PREDEFINED_TEXTS
from luciotech.services.customer_service import CustomerData
from luciotech.services.equipment_service import EquipmentData
from luciotech.services.predefined_text_service import save_predefined_texts
from luciotech.services.reception_service import ReceptionData, register_reception
from luciotech.ui.dialogs.order_detail_dialog import OrderDetailDialog
from luciotech.ui.widgets.rich_text_editor import RichTextEditor


@pytest.fixture
def order_id(session_factory: sessionmaker[Session]) -> int:
    with session_factory() as session:
        order = register_reception(
            session,
            ReceptionData(
                equipment=EquipmentData(cliente_id=None, tipo_equipo="Laptop"),
                new_customer=CustomerData(nombre_completo="Ana Torres", telefono_principal="0991234567"),
                fecha_ingreso=datetime(2026, 3, 10, 9, 0),
            ),
        )
        session.commit()
        return order.id


def test_insert_predefined_text_in_empty_editor(qtbot: QtBot) -> None:
    editor = RichTextEditor(predefined=["Se verificó la memoria RAM."])
    qtbot.addWidget(editor)
    editor.insert_predefined("Se verificó la memoria RAM.")
    assert editor.editor.toPlainText() == "Se verificó la memoria RAM."


def test_insert_predefined_starts_new_paragraph_when_text_exists(qtbot: QtBot) -> None:
    editor = RichTextEditor()
    qtbot.addWidget(editor)
    editor.set_html("<p>Primera nota</p>")
    editor.insert_predefined("Se verificó la memoria RAM.")
    assert editor.editor.toPlainText() == "Primera nota\nSe verificó la memoria RAM."


def test_menu_lists_the_configured_texts(qtbot: QtBot) -> None:
    editor = RichTextEditor(predefined=["Uno.", "Dos."])
    qtbot.addWidget(editor)
    editor._fill_predefined_menu()
    labels = [action.text() for action in editor._predefined_menu.actions()]
    assert labels == ["Uno.", "Dos."]


def test_menu_shows_disabled_hint_when_no_texts(qtbot: QtBot) -> None:
    editor = RichTextEditor(predefined=[])
    qtbot.addWidget(editor)
    editor._fill_predefined_menu()
    actions = editor._predefined_menu.actions()
    assert len(actions) == 1
    assert not actions[0].isEnabled()


def test_clicking_a_menu_entry_inserts_it(qtbot: QtBot) -> None:
    editor = RichTextEditor(predefined=["Uno."])
    qtbot.addWidget(editor)
    editor._fill_predefined_menu()
    editor._predefined_menu.actions()[0].trigger()
    assert editor.editor.toPlainText() == "Uno."


def test_detail_dialog_uses_saved_predefined_texts(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        save_predefined_texts(session, ["Cambio de pasta térmica."])
        session.commit()
    dialog = OrderDetailDialog(session_factory, order_id, "Ing. Lucio")
    qtbot.addWidget(dialog)
    assert dialog._diagnosis.predefined_texts() == ["Cambio de pasta térmica."]
    assert dialog._work_performed.predefined_texts() == ["Cambio de pasta térmica."]


def test_detail_dialog_defaults_are_the_specified_seven(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    dialog = OrderDetailDialog(session_factory, order_id, "Ing. Lucio")
    qtbot.addWidget(dialog)
    assert dialog._recommendations.predefined_texts() == list(DEFAULT_PREDEFINED_TEXTS)
