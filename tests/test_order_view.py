"""Pruebas del paso 8: datos de las pestañas Cliente y Equipo de la vista de orden."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from PyQt6.QtWidgets import QGroupBox, QLabel, QScrollArea
from pytestqt.qtbot import QtBot
from sqlalchemy.orm import Session, sessionmaker

from luciotech.database.enums import OrderState
from luciotech.database.models import ServiceOrder
from luciotech.services.customer_service import CustomerData, save_customer
from luciotech.services.equipment_service import EquipmentData, save_equipment
from luciotech.services.order_view_service import customer_view, equipment_view
from luciotech.services.reception_service import ReceptionData, register_reception
from luciotech.services.state_service import change_order_state
from luciotech.ui.dialogs.order_detail_dialog import HISTORY_MIN_HEIGHT, OrderDetailDialog


@pytest.fixture
def two_orders(session_factory: sessionmaker[Session], tax_enabled: None) -> tuple[int, int]:
    """Cliente con dos órdenes, con IVA del 15 %: la primera con saldo 95, la segunda
    cancelada con saldo 115."""
    with session_factory() as session:
        first = register_reception(
            session,
            ReceptionData(
                equipment=EquipmentData(
                    cliente_id=None, tipo_equipo="Laptop", marca="Dell", modelo="Inspiron 1750",
                    numero_serie="SN-1", contrasena_equipo="1234", accesorios_recibidos="cargador",
                    problema_reportado_cliente="no carga", color="Negro",
                ),
                new_customer=CustomerData(nombre_completo="Jean Carlos", numero_identificacion="1301206320",
                                          telefono_principal="0978907244", correo_electronico="jc@correo.com"),
                fecha_ingreso=datetime(2026, 3, 10, 9, 0),
                costo_diagnostico=Decimal("100"),
                anticipo=Decimal("20"),
            ),
        )
        second = register_reception(
            session,
            ReceptionData(
                equipment=EquipmentData(cliente_id=None, tipo_equipo="Impresora"),
                customer_id=first.cliente_id,
                fecha_ingreso=datetime(2026, 3, 11, 9, 0),
                costo_diagnostico=Decimal("100"),
            ),
        )
        change_order_state(session, second, OrderState.CANCELADO, usuario="Ing. Lucio")
        session.commit()
        return first.id, second.id


def test_customer_view_lists_other_orders_and_balance(
    session_factory: sessionmaker[Session], two_orders: tuple[int, int]
) -> None:
    first_id, second_id = two_orders
    with session_factory() as session:
        order = session.get(ServiceOrder, first_id)
        view = customer_view(session, order)
        assert view.nombre_completo == "Jean Carlos"
        assert view.correo_electronico == "jc@correo.com"
        assert view.otras_ordenes == [session.get(ServiceOrder, second_id).numero_orden]
        # La cancelada no suma saldo: solo los 95 de la primera.
        assert view.saldo_pendiente_total == Decimal("95.00")


def test_equipment_view_exposes_technical_data(
    session_factory: sessionmaker[Session], two_orders: tuple[int, int]
) -> None:
    first_id, _ = two_orders
    with session_factory() as session:
        view = equipment_view(session.get(ServiceOrder, first_id))
        assert view.marca == "Dell"
        assert view.modelo == "Inspiron 1750"
        assert view.numero_serie == "SN-1"
        assert view.accesorios_recibidos == "cargador"
        assert view.problema_reportado_cliente == "no carga"
        assert view.contrasena_equipo == "1234"


def test_customer_view_without_other_orders_is_empty_list(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        order = register_reception(
            session,
            ReceptionData(
                equipment=EquipmentData(cliente_id=None, tipo_equipo="Laptop"),
                new_customer=CustomerData(nombre_completo="Solo Una Vez", telefono_principal="0991234567"),
                fecha_ingreso=datetime(2026, 4, 1, 9, 0),
            ),
        )
        session.commit()
        assert customer_view(session, order).otras_ordenes == []


def test_detail_dialog_groups_everything_in_three_tabs(
    qtbot: QtBot, session_factory: sessionmaker[Session], two_orders: tuple[int, int]
) -> None:
    """Nueve pestañas del mismo peso se buscaban a ciegas; ahora son tres áreas y dentro de
    «Trabajo» se turnan las cuatro superficies de escritura."""
    first_id, _ = two_orders
    dialog = OrderDetailDialog(session_factory, first_id, "Ing. Lucio")
    qtbot.addWidget(dialog)

    names = [dialog._tabs.tabText(i) for i in range(dialog._tabs.count())]
    assert names == ["Resumen", "Trabajo", "Dinero"]

    work = [dialog._work_tabs.tabText(i) for i in range(dialog._work_tabs.count())]
    assert work == ["Diagnóstico", "Reparación", "Recomendaciones", "Fotografías"]

    # Las secciones de consulta viven en la página del resumen, no en pestañas sueltas.
    sections = [
        box.title() for box in dialog._tabs.widget(0).widget().findChildren(QGroupBox)
    ]
    assert sections == ["Siguiente paso", "Orden", "Cliente", "Equipo", "Historial"]


def test_the_summary_page_is_the_only_one_that_scrolls(
    qtbot: QtBot, session_factory: sessionmaker[Session], two_orders: tuple[int, int]
) -> None:
    """El resumen se lee como una ficha larga; el trabajo y el dinero necesitan el alto entero."""
    first_id, _ = two_orders
    dialog = OrderDetailDialog(session_factory, first_id, "Ing. Lucio")
    qtbot.addWidget(dialog)
    assert isinstance(dialog._tabs.widget(0), QScrollArea)
    assert not isinstance(dialog._tabs.widget(1), QScrollArea)
    assert not isinstance(dialog._tabs.widget(2), QScrollArea)


def test_the_history_is_visible_without_leaving_the_summary(
    qtbot: QtBot, session_factory: sessionmaker[Session], two_orders: tuple[int, int]
) -> None:
    first_id, _ = two_orders
    dialog = OrderDetailDialog(session_factory, first_id, "Ing. Lucio")
    qtbot.addWidget(dialog)
    assert dialog._history.rowCount() >= 1
    assert dialog._history.minimumHeight() == HISTORY_MIN_HEIGHT
    assert dialog._tabs.widget(0).widget().isAncestorOf(dialog._history)


def test_equipment_tab_hides_password_until_toggled(
    qtbot: QtBot, session_factory: sessionmaker[Session], two_orders: tuple[int, int]
) -> None:
    first_id, _ = two_orders
    dialog = OrderDetailDialog(session_factory, first_id, "Ing. Lucio")
    qtbot.addWidget(dialog)
    assert "1234" not in dialog._equipment_text.text()
    assert "••••••" in dialog._equipment_text.text()

    dialog._toggle_password.setChecked(True)
    assert "1234" in dialog._equipment_text.text()
    assert dialog._toggle_password.text() == "Ocultar contraseña"


def test_customer_tab_shows_contact_and_balance(
    qtbot: QtBot, session_factory: sessionmaker[Session], two_orders: tuple[int, int]
) -> None:
    first_id, _ = two_orders
    dialog = OrderDetailDialog(session_factory, first_id, "Ing. Lucio")
    qtbot.addWidget(dialog)
    text = dialog._customer_text.text()
    assert "Jean Carlos" in text
    assert "0978907244" in text
    assert "95.00 USD" in text


def test_user_text_is_escaped_in_html(
    qtbot: QtBot, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        order = register_reception(
            session,
            ReceptionData(
                equipment=EquipmentData(cliente_id=None, tipo_equipo="Laptop",
                                        problema_reportado_cliente="<b>negrita</b>"),
                new_customer=CustomerData(nombre_completo="<i>Ana</i>", telefono_principal="0991234567"),
                fecha_ingreso=datetime(2026, 3, 10, 9, 0),
            ),
        )
        session.commit()
        order_id = order.id
    dialog = OrderDetailDialog(session_factory, order_id, "Ing. Lucio")
    qtbot.addWidget(dialog)
    assert "&lt;i&gt;Ana&lt;/i&gt;" in dialog._customer_text.text()
    assert "&lt;b&gt;negrita&lt;/b&gt;" in dialog._equipment_text.text()
