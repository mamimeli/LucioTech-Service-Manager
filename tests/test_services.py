"""Pruebas del paso 4: repositorios, numeración, estados, totales, duplicados y borrado lógico."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from luciotech.config import DEFAULT_TAX_PERCENT
from luciotech.database.connection import create_db_engine, create_session_factory
from luciotech.database.enums import OrderState, PaymentMethod, PaymentType
from luciotech.database.models import Base, Customer, Equipment, Payment, ServiceOrder, StateHistory
from luciotech.database.repositories import (
    CustomerRepository,
    EquipmentRepository,
    ServiceOrderRepository,
)
from luciotech.services.customer_service import find_possible_duplicates
from luciotech.services.equipment_service import find_orders_with_serial
from luciotech.services.order_number_service import next_order_number
from luciotech.services.order_service import (
    create_service_order,
    restore_order,
    soft_delete_order,
)
from luciotech.services.settings_service import (
    KEY_TAX_ENABLED,
    KEY_TAX_PERCENT,
    TaxSettings,
    set_value,
    tax_settings,
)
from luciotech.services.state_service import change_order_state
from luciotech.services.totals_service import (
    calculate_totals,
    net_payments,
    recalculate_order_totals,
    recalculate_stored_totals,
)

ENTRY = datetime(2026, 3, 10, 9, 0)
TAX_15 = TaxSettings(percent=Decimal("15"), enabled=True)
NO_TAX = TaxSettings(percent=Decimal("15"), enabled=False)


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine: Engine = create_db_engine(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    Base.metadata.create_all(engine)
    with create_session_factory(engine)() as db_session:
        yield db_session
    engine.dispose()


def make_customer(
    session: Session,
    nombre: str = "Juan Pérez",
    ident: str | None = "1710034065",
    telefono: str | None = "0991234567",
) -> Customer:
    return CustomerRepository(session).add(
        Customer(nombre_completo=nombre, numero_identificacion=ident, telefono_principal=telefono)
    )


def make_equipment(session: Session, customer: Customer, serie: str = "SN-ABC-123") -> Equipment:
    return EquipmentRepository(session).add(
        Equipment(customer=customer, tipo_equipo="Laptop", marca="HP", numero_serie=serie)
    )


def make_order(
    session: Session,
    costo: Decimal = Decimal("100.00"),
    anticipo: Decimal = Decimal("0.00"),
    serie: str = "SN-ABC-123",
) -> ServiceOrder:
    customer = make_customer(session)
    equipment = make_equipment(session, customer, serie)
    return create_service_order(
        session,
        customer=customer,
        equipment=equipment,
        usuario="Ing. Lucio",
        fecha_ingreso=ENTRY,
        costo_diagnostico=costo,
        anticipo=anticipo,
    )


# Numeración de órdenes


def test_order_numbers_are_sequential_and_padded(session: Session) -> None:
    assert next_order_number(session, 2026) == "OT-2026-000001"
    assert next_order_number(session, 2026) == "OT-2026-000002"


def test_order_numbers_restart_each_year(session: Session) -> None:
    next_order_number(session, 2026)
    next_order_number(session, 2026)
    assert next_order_number(session, 2027) == "OT-2027-000001"


def test_order_number_is_released_when_transaction_is_rolled_back(session: Session) -> None:
    make_order(session)
    session.rollback()
    assert make_order(session).numero_orden == "OT-2026-000001"


def test_created_orders_get_distinct_numbers_and_initial_history(session: Session) -> None:
    first = make_order(session)
    second = make_order(session)

    assert first.numero_orden == "OT-2026-000001"
    assert second.numero_orden == "OT-2026-000002"
    assert len(first.state_changes) == 1
    initial = first.state_changes[0]
    assert initial.estado_anterior is None
    assert initial.estado_nuevo == OrderState.RECIBIDO


def test_estimated_delivery_before_entry_is_rejected(session: Session) -> None:
    customer = make_customer(session)
    equipment = make_equipment(session, customer)
    with pytest.raises(ValueError):
        create_service_order(
            session,
            customer=customer,
            equipment=equipment,
            usuario="Ing. Lucio",
            fecha_ingreso=ENTRY,
            fecha_estimada_entrega=datetime(2026, 3, 9),
        )


def test_equipment_must_belong_to_the_customer(session: Session) -> None:
    owner = make_customer(session, nombre="Ana")
    other = make_customer(session, nombre="Luis")
    equipment = make_equipment(session, owner)
    with pytest.raises(ValueError):
        create_service_order(
            session,
            customer=other,
            equipment=equipment,
            usuario="Ing. Lucio",
            fecha_ingreso=ENTRY,
        )


# Cambios de estado e historial


def test_state_change_records_previous_and_new_state(session: Session) -> None:
    order = make_order(session)

    entry = change_order_state(
        session, order, OrderState.DIAGNOSTICADO, usuario="Ing. Lucio", comentario="Disco dañado"
    )

    assert entry is not None
    assert order.estado == OrderState.DIAGNOSTICADO
    assert entry.estado_anterior == OrderState.RECIBIDO
    assert entry.estado_nuevo == OrderState.DIAGNOSTICADO
    assert len(order.state_changes) == 2


def test_same_state_is_not_recorded(session: Session) -> None:
    order = make_order(session)
    assert change_order_state(session, order, OrderState.RECIBIDO, usuario="Ing. Lucio") is None
    assert len(order.state_changes) == 1


def test_invalid_state_is_rejected(session: Session) -> None:
    order = make_order(session)
    with pytest.raises(ValueError):
        change_order_state(session, order, "Inventado", usuario="Ing. Lucio")


def test_history_is_kept_when_order_is_edited(session: Session) -> None:
    order = make_order(session)
    change_order_state(session, order, OrderState.EN_REPARACION, usuario="Ing. Lucio")

    order.problema_reportado = "No enciende"
    session.commit()

    count = session.scalar(
        select(func.count()).select_from(StateHistory).where(StateHistory.orden_id == order.id)
    )
    assert count == 2


# Totales


def test_totals_apply_discount_tax_and_anticipo() -> None:
    totals = calculate_totals(
        costo_diagnostico=Decimal("20"),
        descuento=Decimal("10"),
        anticipo=Decimal("20"),
        pagos_realizados=Decimal("0"),
        tax=TAX_15,
        line_items_total=Decimal("80"),
    )
    assert totals.subtotal == Decimal("100.00")
    assert totals.impuestos == Decimal("15.00")
    assert totals.total == Decimal("105.00")
    assert totals.saldo_pendiente == Decimal("85.00")


def test_totals_without_tax_when_disabled() -> None:
    totals = calculate_totals(
        costo_diagnostico=Decimal("20"),
        descuento=Decimal("10"),
        anticipo=Decimal("0"),
        pagos_realizados=Decimal("0"),
        tax=NO_TAX,
        line_items_total=Decimal("80"),
    )
    assert totals.impuestos == Decimal("0.00")
    assert totals.total == Decimal("90.00")
    assert totals.saldo_pendiente == Decimal("90.00")


def test_tax_is_rounded_half_up_to_cents() -> None:
    totals = calculate_totals(
        costo_diagnostico=Decimal("10.01"),
        descuento=Decimal("0"),
        anticipo=Decimal("0"),
        pagos_realizados=Decimal("0"),
        tax=TAX_15,
    )
    assert totals.impuestos == Decimal("1.50")
    assert totals.total == Decimal("11.51")


def test_negative_amounts_are_rejected() -> None:
    with pytest.raises(ValueError):
        calculate_totals(
            costo_diagnostico=Decimal("10"),
            descuento=Decimal("-1"),
            anticipo=Decimal("0"),
            pagos_realizados=Decimal("0"),
            tax=TAX_15,
        )


def test_balance_updates_after_payment_and_refund(session: Session) -> None:
    set_value(session, KEY_TAX_ENABLED, "true")
    order = make_order(session, costo=Decimal("100.00"), anticipo=Decimal("20.00"))
    assert order.total == Decimal("115.00")
    assert order.saldo_pendiente == Decimal("95.00")

    Payment(
        order=order,
        tipo_pago=PaymentType.ABONO.value,
        metodo_pago=PaymentMethod.EFECTIVO.value,
        monto=Decimal("50.00"),
    )
    recalculate_order_totals(order, TAX_15)
    assert order.saldo_pendiente == Decimal("45.00")

    Payment(
        order=order,
        tipo_pago=PaymentType.REEMBOLSO.value,
        metodo_pago=PaymentMethod.EFECTIVO.value,
        monto=Decimal("10.00"),
    )
    recalculate_order_totals(order, TAX_15)
    assert net_payments(order) == Decimal("40.00")
    assert order.saldo_pendiente == Decimal("55.00")


# Configuración de impuestos


def test_tax_defaults_come_from_config_when_not_stored(session: Session) -> None:
    """El IVA nace desactivado: los precios del taller ya lo llevan incluido."""
    assert tax_settings(session) == TaxSettings(percent=DEFAULT_TAX_PERCENT, enabled=False)


def test_new_order_with_default_settings_adds_no_tax(session: Session) -> None:
    order = make_order(session, costo=Decimal("100.00"))
    assert order.impuestos == Decimal("0.00")
    assert order.total == Decimal("100.00")


def test_stored_totals_are_brought_up_to_date_when_tax_is_switched_off(
    session: Session,
) -> None:
    """Al cambiar el IVA, las órdenes guardadas no pueden quedarse con las cifras anteriores."""
    set_value(session, KEY_TAX_ENABLED, "true")
    order = make_order(session, costo=Decimal("100.00"), anticipo=Decimal("20.00"))
    assert order.total == Decimal("115.00")

    set_value(session, KEY_TAX_ENABLED, "false")
    assert recalculate_stored_totals(session, tax_settings(session)) == 1
    assert order.impuestos == Decimal("0.00")
    assert order.total == Decimal("100.00")
    assert order.saldo_pendiente == Decimal("80.00")
    # La segunda pasada no encuentra nada que corregir.
    assert recalculate_stored_totals(session, tax_settings(session)) == 0


def test_tax_can_be_changed_and_disabled_for_new_orders(session: Session) -> None:
    set_value(session, KEY_TAX_PERCENT, "12")
    set_value(session, KEY_TAX_ENABLED, "false")
    assert tax_settings(session) == TaxSettings(percent=Decimal("12"), enabled=False)

    order = make_order(session, costo=Decimal("100"))
    assert order.impuestos == Decimal("0.00")
    assert order.total == Decimal("100.00")


# Borrado lógico y repositorios


def test_soft_delete_hides_order_and_restore_brings_it_back(session: Session) -> None:
    order = make_order(session)
    repo = ServiceOrderRepository(session)

    soft_delete_order(session, order, when=datetime(2026, 3, 11, 8, 0))
    assert order.activo is False
    assert order.fecha_eliminacion == datetime(2026, 3, 11, 8, 0)
    assert order.estado == OrderState.RECIBIDO
    assert order not in repo.list_active()
    assert order in repo.list_deleted()

    restore_order(session, order)
    assert order.activo is True
    assert order.fecha_eliminacion is None
    assert order in repo.list_active()


def test_customer_crud_through_repository(session: Session) -> None:
    repo = CustomerRepository(session)
    customer = repo.add(Customer(nombre_completo="Ana", numero_identificacion="1710034065"))
    customer_id = customer.id
    assert repo.get(customer_id) is customer

    customer.telefono_principal = "0999999999"
    repo.save(customer)
    session.commit()
    session.expire_all()
    stored = repo.get(customer_id)
    assert stored is not None
    assert stored.telefono_principal == "0999999999"

    repo.delete(stored)
    session.commit()
    assert repo.get(customer_id) is None


# Duplicados


def test_duplicate_customer_by_identification(session: Session) -> None:
    existing = make_customer(session, ident="1710034065", telefono="0991234567")
    assert find_possible_duplicates(session, numero_identificacion="1710034065") == [existing]


def test_duplicate_customer_by_phone_ignores_formatting(session: Session) -> None:
    existing = make_customer(session, telefono="0991234567")
    assert find_possible_duplicates(session, telefono="099 123-4567") == [existing]


def test_no_duplicate_when_nothing_matches(session: Session) -> None:
    make_customer(session, ident="1710034065", telefono="0991234567")
    assert (
        find_possible_duplicates(session, numero_identificacion="0926687856", telefono="0987654321")
        == []
    )


def test_duplicate_serial_returns_existing_active_orders(session: Session) -> None:
    order = make_order(session, serie="SN-ABC-123")

    assert find_orders_with_serial(session, " sn-abc-123 ") == [order]
    assert find_orders_with_serial(session, "OTRO") == []
    assert find_orders_with_serial(session, "") == []

    soft_delete_order(session, order)
    assert find_orders_with_serial(session, "SN-ABC-123") == []
