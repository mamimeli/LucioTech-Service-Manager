"""Pruebas de los textos clínicos de la orden: servicio y pestañas Diagnóstico y Reparación."""

from __future__ import annotations

from datetime import datetime

import pytest
from pytestqt.qtbot import QtBot
from sqlalchemy.orm import Session, sessionmaker

from luciotech.database.models import ServiceOrder
from luciotech.services.clinical_text_service import (
    ClinicalTexts,
    get_clinical_texts,
    save_clinical_texts,
)
from luciotech.services.customer_service import CustomerData
from luciotech.services.equipment_service import EquipmentData
from luciotech.services.reception_service import ReceptionData, register_reception
from luciotech.ui.dialogs.order_detail_dialog import OrderDetailDialog


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


def test_new_order_has_empty_clinical_texts(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        texts = get_clinical_texts(session.get(ServiceOrder, order_id))
    assert texts == ClinicalTexts("", "", "")


def test_clinical_texts_round_trip_through_database(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order_id)
        save_clinical_texts(
            session,
            order,
            ClinicalTexts("<p><b>Disco</b> dañado</p>", "<p>Cambio de disco</p>", "<p>Respaldar</p>"),
        )
        session.commit()
    with session_factory() as session:
        texts = get_clinical_texts(session.get(ServiceOrder, order_id))
    assert texts.diagnostico_html == "<p><b>Disco</b> dañado</p>"
    assert texts.trabajo_realizado_html == "<p>Cambio de disco</p>"
    assert texts.recomendaciones_html == "<p>Respaldar</p>"


def test_dialog_shows_saved_texts(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        save_clinical_texts(
            session,
            session.get(ServiceOrder, order_id),
            ClinicalTexts("<p>Disco dañado</p>", "<p>Reemplazo</p>", "<p>Respaldo</p>"),
        )
        session.commit()
    dialog = OrderDetailDialog(session_factory, order_id, "Ing. Lucio")
    qtbot.addWidget(dialog)
    assert dialog._diagnosis.editor.toPlainText() == "Disco dañado"
    assert dialog._work_performed.editor.toPlainText() == "Reemplazo"
    assert dialog._recommendations.editor.toPlainText() == "Respaldo"


def test_saving_in_dialog_persists_edited_text(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    dialog = OrderDetailDialog(session_factory, order_id, "Ing. Lucio")
    qtbot.addWidget(dialog)
    dialog._diagnosis.set_html("<p>Placa con <i>corto</i></p>")
    dialog._save_clinical_texts()
    with session_factory() as session:
        stored = get_clinical_texts(session.get(ServiceOrder, order_id))
    assert "Placa con" in stored.diagnostico_html
    assert "font-style:italic" in stored.diagnostico_html
    assert dialog._message.text() == "Guardado."


def test_refresh_does_not_overwrite_unsaved_text(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    dialog = OrderDetailDialog(session_factory, order_id, "Ing. Lucio")
    qtbot.addWidget(dialog)
    dialog._work_performed.set_html("<p>Texto sin guardar</p>")
    dialog.refresh()
    assert dialog._work_performed.editor.toPlainText() == "Texto sin guardar"


def test_saved_text_survives_reopening(
    qtbot: QtBot, session_factory: sessionmaker[Session], order_id: int
) -> None:
    first = OrderDetailDialog(session_factory, order_id, "Ing. Lucio")
    qtbot.addWidget(first)
    first._recommendations.set_html("<p>Cambiar batería</p>")
    first._save_clinical_texts()

    second = OrderDetailDialog(session_factory, order_id, "Ing. Lucio")
    qtbot.addWidget(second)
    assert second._recommendations.editor.toPlainText() == "Cambiar batería"
