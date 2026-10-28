"""Pruebas del paso 6: recepción, filtros de órdenes y accesorios."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker

from luciotech.database.enums import OrderState, Priority
from luciotech.database.models import Customer, Equipment, ServiceOrder
from luciotech.services.accessories import build_accessories_text, suggested_accessories
from luciotech.services.customer_service import CustomerData, save_customer
from luciotech.services.equipment_service import EquipmentData, save_equipment
from luciotech.services.order_number_service import peek_next_order_number
from luciotech.services.order_query_service import OrderFilter, search_orders
from luciotech.services.reception_service import (
    ReceptionData,
    ReceptionValidationError,
    reception_input_errors,
    reception_warnings,
    register_reception,
)
from luciotech.services.state_service import change_order_state

ENTRY = datetime(2026, 3, 10, 9, 0)


def new_customer(**overrides: str | None) -> CustomerData:
    values: dict[str, str | None] = {
        "nombre_completo": "Juan Pérez",
        "numero_identificacion": "1710034065",
        "telefono_principal": "0991234567",
    }
    values.update(overrides)
    return CustomerData(**values)  # type: ignore[arg-type]


def equipment(**overrides: str | None) -> EquipmentData:
    values: dict[str, str | None] = {"tipo_equipo": "Laptop", "marca": "HP", "modelo": "15"}
    values.update(overrides)
    return EquipmentData(cliente_id=None, **values)  # type: ignore[arg-type]


def reception(**overrides: object) -> ReceptionData:
    base: dict[str, object] = {
        "equipment": equipment(problema_reportado_cliente="No enciende"),
        "new_customer": new_customer(),
        "fecha_ingreso": ENTRY,
    }
    base.update(overrides)
    return ReceptionData(**base)  # type: ignore[arg-type]


def seed_customer(session_factory: sessionmaker[Session], **overrides: str | None) -> int:
    with session_factory() as session:
        customer = save_customer(session, new_customer(**overrides))
        session.commit()
        return customer.id


# Validación de la recepción


def test_reception_requires_exactly_one_customer_source(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        neither = reception(new_customer=None)
        assert reception_input_errors(session, neither) == {"cliente": "customer.required"}

        both = reception(customer_id=1)
        assert reception_input_errors(session, both) == {"cliente": "customer.required"}


def test_reception_rejects_unknown_existing_customer(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        data = reception(new_customer=None, customer_id=999)
        assert reception_input_errors(session, data) == {"cliente": "not_found"}


def test_reception_rejects_estimate_before_entry(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        data = reception(fecha_estimada_entrega=ENTRY - timedelta(days=1))
        assert reception_input_errors(session, data) == {"fecha_estimada_entrega": "date.before_entry"}


def test_reception_rejects_negative_amounts(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        data = reception(costo_diagnostico=Decimal("-1"), anticipo=Decimal("-2"))
        errors = reception_input_errors(session, data)
        assert errors == {"costo_diagnostico": "amount.negative", "anticipo": "amount.negative"}


def test_anticipo_cannot_exceed_total_with_tax(
    session_factory: sessionmaker[Session], tax_enabled: None
) -> None:
    with session_factory() as session:
        data = reception(costo_diagnostico=Decimal("100"), anticipo=Decimal("116"))
        assert reception_input_errors(session, data) == {"anticipo": "anticipo.exceeds_total"}

        ok = reception(costo_diagnostico=Decimal("100"), anticipo=Decimal("115"))
        assert reception_input_errors(session, ok) == {}


def test_equipment_type_and_missing_problem_are_checked(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        data = reception(equipment=equipment(tipo_equipo="Televisor"))
        assert reception_input_errors(session, data) == {"tipo_equipo": "invalid_type"}


def test_invalid_new_customer_is_reported(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        data = reception(new_customer=new_customer(numero_identificacion="1710034066"))
        assert reception_input_errors(session, data) == {
            "numero_identificacion": "cedula.check_digit"
        }


# Registro de la recepción


def test_register_reception_with_new_customer_creates_everything(
    session_factory: sessionmaker[Session], tax_enabled: None
) -> None:
    with session_factory() as session:
        order = register_reception(
            session,
            reception(costo_diagnostico=Decimal("20"), anticipo=Decimal("5")),
        )
        session.commit()

        assert order.numero_orden == "OT-2026-000001"
        assert order.estado == OrderState.RECIBIDO
        assert order.problema_reportado == "No enciende"
        assert order.tecnico_responsable == "Ing. Lucio"
        assert order.customer.nombre_completo == "Juan Pérez"
        assert order.equipment.customer is order.customer
        assert order.total == Decimal("23.00")
        assert order.saldo_pendiente == Decimal("18.00")


def test_register_reception_with_existing_customer(session_factory: sessionmaker[Session]) -> None:
    customer_id = seed_customer(session_factory)
    with session_factory() as session:
        order = register_reception(session, reception(new_customer=None, customer_id=customer_id))
        session.commit()
        assert order.cliente_id == customer_id
        assert session.query(Customer).count() == 1


def test_failed_reception_creates_nothing(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        with pytest.raises(ReceptionValidationError):
            register_reception(session, reception(costo_diagnostico=Decimal("-5")))
        session.rollback()
        assert session.query(Customer).count() == 0
        assert session.query(ServiceOrder).count() == 0


def test_reception_uses_entry_year_for_number(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        order = register_reception(session, reception(fecha_ingreso=datetime(2027, 1, 2, 8, 0)))
        session.commit()
        assert order.numero_orden == "OT-2027-000001"


def test_peek_does_not_reserve_the_number(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        assert peek_next_order_number(session, 2026) == "OT-2026-000001"
        assert peek_next_order_number(session, 2026) == "OT-2026-000001"
        register_reception(session, reception())
        session.commit()
        assert peek_next_order_number(session, 2026) == "OT-2026-000002"


def test_priority_is_stored(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        order = register_reception(session, reception(prioridad=Priority.URGENTE))
        session.commit()
        assert order.prioridad == Priority.URGENTE


# Advertencias no bloqueantes


def test_warnings_report_similar_customer_and_serial(session_factory: sessionmaker[Session]) -> None:
    customer_id = seed_customer(session_factory)
    with session_factory() as session:
        first = register_reception(
            session,
            reception(new_customer=None, customer_id=customer_id,
                      equipment=equipment(numero_serie="SN-77")),
        )
        session.commit()
        assert first.equipment.numero_serie == "SN-77"

        data = reception(
            new_customer=new_customer(numero_identificacion="", telefono_principal="0991234567"),
            equipment=equipment(numero_serie="sn-77"),
        )
        warnings = reception_warnings(session, data)
        assert warnings.has_any
        assert [c.id for c in warnings.duplicate_customers] == [customer_id]
        assert [o.numero_orden for o in warnings.serial_orders] == ["OT-2026-000001"]


def test_warnings_are_empty_for_fresh_data(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        warnings = reception_warnings(session, reception(equipment=equipment(numero_serie="NEW-1")))
        assert not warnings.has_any


# Filtros de la lista de órdenes


@pytest.fixture
def three_orders(session_factory: sessionmaker[Session]) -> sessionmaker[Session]:
    with session_factory() as session:
        ana = register_reception(
            session,
            reception(new_customer=new_customer(nombre_completo="Ana Torres",
                                                numero_identificacion="", telefono_principal="0999000111"),
                      equipment=equipment(marca="Dell", modelo="Inspiron", tipo_equipo="Laptop"),
                      costo_diagnostico=Decimal("10"), prioridad=Priority.ALTA),
        )
        register_reception(
            session,
            reception(new_customer=new_customer(nombre_completo="Luis Mora",
                                                numero_identificacion="", telefono_principal="0988000222"),
                      equipment=equipment(marca="Epson", modelo="L3150", tipo_equipo="Impresora"),
                      fecha_ingreso=ENTRY + timedelta(days=1)),
        )
        change_order_state(session, ana, OrderState.EN_REPARACION, usuario="Ing. Lucio")
        session.commit()
    return session_factory


def _numbers(session_factory: sessionmaker[Session], flt: OrderFilter) -> list[str]:
    with session_factory() as session:
        return [order.numero_orden for order in search_orders(session, flt)]


def test_list_is_newest_first(three_orders: sessionmaker[Session]) -> None:
    assert _numbers(three_orders, OrderFilter()) == ["OT-2026-000002", "OT-2026-000001"]


def test_text_search_matches_customer_brand_and_phone(three_orders: sessionmaker[Session]) -> None:
    assert _numbers(three_orders, OrderFilter(text="ana")) == ["OT-2026-000001"]
    assert _numbers(three_orders, OrderFilter(text="epson")) == ["OT-2026-000002"]
    assert _numbers(three_orders, OrderFilter(text="0988000222")) == ["OT-2026-000002"]


def test_text_search_treats_wildcards_literally(three_orders: sessionmaker[Session]) -> None:
    assert _numbers(three_orders, OrderFilter(text="%")) == []


def test_state_and_type_filters_combine(three_orders: sessionmaker[Session]) -> None:
    flt = OrderFilter(estado=OrderState.EN_REPARACION.value, tipo_equipo="Laptop")
    assert _numbers(three_orders, flt) == ["OT-2026-000001"]
    flt = OrderFilter(estado=OrderState.EN_REPARACION.value, tipo_equipo="Impresora")
    assert _numbers(three_orders, flt) == []


def test_priority_filter(three_orders: sessionmaker[Session]) -> None:
    assert _numbers(three_orders, OrderFilter(prioridad=Priority.ALTA.value)) == ["OT-2026-000001"]


def test_balance_filter(three_orders: sessionmaker[Session]) -> None:
    assert _numbers(three_orders, OrderFilter(solo_con_saldo=True)) == ["OT-2026-000001"]


def test_deleted_orders_are_hidden_unless_requested(three_orders: sessionmaker[Session]) -> None:
    with three_orders() as session:
        order = session.get(ServiceOrder, 1)
        order.activo = False
        session.commit()
    assert _numbers(three_orders, OrderFilter()) == ["OT-2026-000002"]
    assert _numbers(three_orders, OrderFilter(incluir_eliminadas=True)) == [
        "OT-2026-000002",
        "OT-2026-000001",
    ]


# Accesorios


def test_accessories_depend_on_equipment_type() -> None:
    assert "Cargador" in suggested_accessories("Laptop")
    assert "Antena" in suggested_accessories("Cámara de seguridad")
    assert suggested_accessories("Tipo desconocido") == ("Otro",)


def test_accessories_text_joins_selection_and_manual_input() -> None:
    assert build_accessories_text(["Cargador", "Bolso"], " Adaptador HDMI ") == (
        "Cargador, Bolso, Adaptador HDMI"
    )
    assert build_accessories_text([], "  ") is None


def test_accessories_text_includes_detail_of_each_item() -> None:
    text = build_accessories_text(
        ["Batería", "Cargador"],
        None,
        details={"Batería": " Dell XPS 13 ", "Cargador": "  "},
    )
    assert text == "Batería (Dell XPS 13), Cargador"


def test_reception_can_reuse_existing_equipment_of_the_customer(
    session_factory: sessionmaker[Session],
) -> None:
    customer_id = seed_customer(session_factory)
    with session_factory() as session:
        first = register_reception(
            session,
            reception(new_customer=None, customer_id=customer_id,
                      equipment=equipment(numero_serie="SN-REUSE")),
        )
        session.commit()
        equipment_id = first.equipo_id

        second = register_reception(
            session,
            reception(new_customer=None, customer_id=customer_id, equipment_id=equipment_id,
                      equipment=equipment(tipo_equipo="Laptop")),
        )
        session.commit()

        assert second.equipo_id == equipment_id
        assert session.query(Equipment).count() == 1
        assert second.numero_orden == "OT-2026-000002"


def test_reusing_equipment_of_another_customer_is_rejected(
    session_factory: sessionmaker[Session],
) -> None:
    owner_id = seed_customer(session_factory, nombre_completo="Dueño", numero_identificacion="",
                             telefono_principal="0999000001")
    other_id = seed_customer(session_factory, nombre_completo="Otro", numero_identificacion="",
                             telefono_principal="0999000002")
    with session_factory() as session:
        owner_equipment = register_reception(
            session, reception(new_customer=None, customer_id=owner_id),
        )
        session.commit()
        data = reception(new_customer=None, customer_id=other_id,
                         equipment_id=owner_equipment.equipo_id)
        assert reception_input_errors(session, data) == {"equipo": "equipment.other_customer"}


def test_reusing_missing_equipment_is_rejected(session_factory: sessionmaker[Session]) -> None:
    customer_id = seed_customer(session_factory)
    with session_factory() as session:
        data = reception(new_customer=None, customer_id=customer_id, equipment_id=999)
        assert reception_input_errors(session, data) == {"equipo": "not_found"}


def test_equipment_model_is_unchanged_by_reception(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        register_reception(session, reception())
        session.commit()
        assert session.query(Equipment).one().tipo_equipo == "Laptop"
