"""Pruebas de las líneas de presupuesto (§12) y su integración con los totales (§5.3)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker

from luciotech.database.enums import BudgetLineType
from luciotech.database.models import ServiceOrder
from luciotech.services.budget_service import (
    BudgetLineValidationError,
    add_line,
    line_subtotal,
    lines_for_order,
    remove_line,
    set_discount,
    update_line,
)
from luciotech.services.customer_service import CustomerData
from luciotech.services.equipment_service import EquipmentData
from luciotech.services.reception_service import ReceptionData, register_reception
from luciotech.services.settings_service import KEY_TAX_ENABLED, KEY_TAX_PERCENT, set_value


@pytest.fixture
def order_id(session_factory: sessionmaker[Session]) -> int:
    """Orden con diagnóstico de 100 y anticipo de 20: total 115, saldo 95 con IVA del 15%."""
    with session_factory() as session:
        order = register_reception(
            session,
            ReceptionData(
                equipment=EquipmentData(cliente_id=None, tipo_equipo="Laptop"),
                new_customer=CustomerData(nombre_completo="Ana Torres", telefono_principal="0991234567"),
                fecha_ingreso=datetime(2026, 3, 10, 9, 0),
                costo_diagnostico=Decimal("100"),
                anticipo=Decimal("20"),
            ),
        )
        session.commit()
        return order.id


def _order(session: Session, order_id: int) -> ServiceOrder:
    order = session.get(ServiceOrder, order_id)
    assert order is not None
    return order


def test_add_lines_update_order_total_and_balance(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = _order(session, order_id)
        add_line(
            session, order, tipo=BudgetLineType.MANO_OBRA,
            descripcion="Cambio de disco", cantidad=Decimal("1"), precio_unitario=Decimal("10"),
        )
        add_line(
            session, order, tipo=BudgetLineType.REPUESTO,
            descripcion="SSD 480 GB", cantidad=Decimal("3"), precio_unitario=Decimal("5"),
        )
        session.commit()
        # subtotal 100+25=125; IVA 15% = 18.75; total 143.75; saldo 123.75
        assert order.total == Decimal("143.75")
        assert order.saldo_pendiente == Decimal("123.75")


def test_line_fields_are_stored_clean(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = _order(session, order_id)
        line = add_line(
            session, order, tipo=BudgetLineType.SERVICIO,
            descripcion="  Limpieza interna  ", cantidad=Decimal("2"), precio_unitario=Decimal("15.50"),
        )
        session.commit()
        assert line.tipo_linea == "Servicio"
        assert line.descripcion == "Limpieza interna"
        assert line.cantidad == Decimal("2.00")
        assert line.precio_unitario == Decimal("15.50")
        assert line_subtotal(line) == Decimal("31.00")


def test_update_line_recalculates_total(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = _order(session, order_id)
        line = add_line(
            session, order, tipo=BudgetLineType.MANO_OBRA,
            descripcion="Mano de obra", cantidad=Decimal("1"), precio_unitario=Decimal("50"),
        )
        session.commit()
        assert order.total == Decimal("172.50")

        update_line(session, line, cantidad=Decimal("2"))
        session.commit()
        assert order.total == Decimal("230.00")
        assert order.saldo_pendiente == Decimal("210.00")


def test_remove_line_recalculates_total(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = _order(session, order_id)
        line = add_line(
            session, order, tipo=BudgetLineType.REPUESTO,
            descripcion="Cable HDMI", cantidad=Decimal("1"), precio_unitario=Decimal("10"),
        )
        session.commit()
        remove_line(session, line)
        session.commit()
        assert order.total == Decimal("115.00")
        assert lines_for_order(session, order_id) == []


def test_line_validation_reports_all_errors(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = _order(session, order_id)
        with pytest.raises(BudgetLineValidationError) as exc:
            add_line(
                session, order, tipo="Inventado", descripcion="   ",
                cantidad=Decimal("0"), precio_unitario=Decimal("-1"),
            )
        assert exc.value.errors == {
            "tipo_linea": "invalid_type",
            "descripcion": "required",
            "cantidad": "amount.must_be_positive",
            "precio_unitario": "amount.negative",
        }


def test_totals_with_discount(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = _order(session, order_id)
        order.descuento = Decimal("10")
        add_line(
            session, order, tipo=BudgetLineType.ACCESORIO,
            descripcion="Fundas protectoras", cantidad=Decimal("2"), precio_unitario=Decimal("12.50"),
        )
        session.commit()
        # subtotal 125, IVA 18.75, descuento 10: 125 - 10 + 18.75 = 133.75
        assert order.total == Decimal("133.75")


def test_totals_with_different_tax_rates(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        set_value(session, KEY_TAX_PERCENT, "12")
        set_value(session, KEY_TAX_ENABLED, "false")
        order = _order(session, order_id)
        add_line(
            session, order, tipo=BudgetLineType.OTRO,
            descripcion="Servicio extra", cantidad=Decimal("1"), precio_unitario=Decimal("25"),
        )
        session.commit()
        assert order.impuestos == Decimal("0.00")
        assert order.total == Decimal("125.00")

        set_value(session, KEY_TAX_ENABLED, "true")
        add_line(
            session, order, tipo=BudgetLineType.OTRO,
            descripcion="Servicio extra 2", cantidad=Decimal("1"), precio_unitario=Decimal("25"),
        )
        session.commit()
        assert order.impuestos == Decimal("18.00")
        assert order.total == Decimal("168.00")


def test_lines_are_listed_in_creation_order(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = _order(session, order_id)
        for description in ("Uno", "Dos", "Tres"):
            add_line(
                session, order, tipo=BudgetLineType.OTRO,
                descripcion=description, cantidad=Decimal("1"), precio_unitario=Decimal("1"),
            )
        session.commit()
        assert [line.descripcion for line in lines_for_order(session, order_id)] == [
            "Uno", "Dos", "Tres",
        ]


def test_set_discount_recalculates_total(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = _order(session, order_id)
        set_discount(session, order, Decimal("15"))
        session.commit()
        # subtotal 100, IVA 15, descuento 15: 100 - 15 + 15 = 100
        assert order.descuento == Decimal("15.00")
        assert order.total == Decimal("100.00")
        assert order.saldo_pendiente == Decimal("80.00")


def test_set_discount_rejects_negative_values(
    session_factory: sessionmaker[Session], order_id: int
) -> None:
    with session_factory() as session:
        order = _order(session, order_id)
        with pytest.raises(BudgetLineValidationError) as exc:
            set_discount(session, order, Decimal("-1"))
        assert exc.value.errors == {"descuento": "amount.negative"}
        assert order.descuento == Decimal("0.00")
