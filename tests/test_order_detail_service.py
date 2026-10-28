"""Pruebas del paso 7: pagos, notas, entrega y línea de tiempo de una orden."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker

from luciotech.database.enums import OrderState, PaymentMethod, PaymentType
from luciotech.database.models import ServiceOrder
from luciotech.services.order_detail_service import (
    PaymentValidationError,
    add_note,
    deposit_warning,
    mark_delivered,
    order_timeline,
    payments_for_order,
    register_payment,
    void_payment,
)
from luciotech.services.reception_service import ReceptionData, register_reception
from luciotech.services.equipment_service import EquipmentData
from luciotech.services.customer_service import CustomerData
from luciotech.services.state_service import change_order_state

ENTRY = datetime(2026, 3, 10, 9, 0)


@pytest.fixture
def order(session_factory: sessionmaker[Session], tax_enabled: None) -> ServiceOrder:
    """Orden con diagnóstico de 100 y anticipo 20, con IVA del 15 %: total 115, saldo 95."""
    with session_factory() as session:
        created = register_reception(
            session,
            ReceptionData(
                equipment=EquipmentData(cliente_id=None, tipo_equipo="Laptop",
                                        problema_reportado_cliente="No enciende"),
                new_customer=CustomerData(nombre_completo="Ana Torres",
                                          telefono_principal="0991234567"),
                fecha_ingreso=ENTRY,
                costo_diagnostico=Decimal("100"),
                anticipo=Decimal("20"),
            ),
        )
        session.commit()
        return created


def test_payment_reduces_balance_and_is_logged(
    session_factory: sessionmaker[Session], order: ServiceOrder
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order.id)
        register_payment(
            session, order, tipo=PaymentType.ABONO, metodo=PaymentMethod.EFECTIVO,
            monto=Decimal("50"), usuario="Ing. Lucio",
        )
        session.commit()

        assert order.saldo_pendiente == Decimal("45.00")
        assert len(order.payments) == 1
        assert any(e.tipo_evento == "Pago recibido" for e in order.events)


def test_full_payment_brings_balance_to_zero(
    session_factory: sessionmaker[Session], order: ServiceOrder
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order.id)
        register_payment(
            session, order, tipo=PaymentType.PAGO_FINAL, metodo=PaymentMethod.TARJETA,
            monto=Decimal("95"), usuario="Ing. Lucio", referencia="  VISA-1  ",
        )
        session.commit()
        assert order.saldo_pendiente == Decimal("0.00")
        assert order.payments[0].referencia == "VISA-1"


def test_refund_cannot_exceed_what_was_paid(
    session_factory: sessionmaker[Session], order: ServiceOrder
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order.id)
        with pytest.raises(PaymentValidationError) as exc:
            register_payment(
                session, order, tipo=PaymentType.REEMBOLSO, metodo=PaymentMethod.EFECTIVO,
                monto=Decimal("5"), usuario="Ing. Lucio",
            )
        assert exc.value.errors == {"monto": "refund.exceeds_paid"}


def test_refund_increases_balance_again(
    session_factory: sessionmaker[Session], order: ServiceOrder
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order.id)
        register_payment(session, order, tipo=PaymentType.ABONO, metodo=PaymentMethod.EFECTIVO,
                         monto=Decimal("30"), usuario="Ing. Lucio")
        register_payment(session, order, tipo=PaymentType.REEMBOLSO, metodo=PaymentMethod.EFECTIVO,
                         monto=Decimal("10"), usuario="Ing. Lucio")
        session.commit()
        assert order.saldo_pendiente == Decimal("75.00")


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-3")])
def test_payment_must_be_positive(
    session_factory: sessionmaker[Session], order: ServiceOrder, amount: Decimal
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order.id)
        with pytest.raises(PaymentValidationError) as exc:
            register_payment(session, order, tipo=PaymentType.ABONO, metodo=PaymentMethod.EFECTIVO,
                             monto=amount, usuario="Ing. Lucio")
        assert exc.value.errors == {"monto": "amount.must_be_positive"}


def test_note_requires_title_and_is_saved(
    session_factory: sessionmaker[Session], order: ServiceOrder
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order.id)
        with pytest.raises(ValueError):
            add_note(session, order, titulo="   ", descripcion="x", usuario="Ing. Lucio")
        add_note(session, order, titulo="  Cliente llamó  ", descripcion=" Pide llamada ",
                 usuario="Ing. Lucio")
        session.commit()
        note = [e for e in order.events if e.titulo == "Cliente llamó"][0]
        assert note.descripcion == "Pide llamada"


def test_mark_delivered_sets_state_date_and_history(
    session_factory: sessionmaker[Session], order: ServiceOrder
) -> None:
    delivered_at = datetime(2026, 3, 15, 16, 30)
    with session_factory() as session:
        order = session.get(ServiceOrder, order.id)
        mark_delivered(session, order, usuario="Ing. Lucio", fecha_entrega=delivered_at)
        session.commit()

        assert order.estado == OrderState.ENTREGADO
        assert order.fecha_entrega == delivered_at
        assert order.state_changes[-1].estado_nuevo == OrderState.ENTREGADO
        assert any(e.tipo_evento == "Equipo entregado" for e in order.events)


def test_timeline_is_chronological_and_keeps_state_changes(
    session_factory: sessionmaker[Session], order: ServiceOrder
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order.id)
        change_order_state(session, order, OrderState.DIAGNOSTICADO, usuario="Ing. Lucio",
                           comentario="Disco dañado")
        add_note(session, order, titulo="Repuesto pedido", descripcion=None, usuario="Ing. Lucio")
        session.commit()

        timeline = order_timeline(order)
        kinds = [entry.kind for entry in timeline]
        assert kinds.count("estado") == 2
        assert kinds.count("evento") == 1
        assert [entry.fecha for entry in timeline] == sorted(entry.fecha for entry in timeline)
        estado_entries = [entry for entry in timeline if entry.kind == "estado"]
        assert any("Disco dañado" in entry.detalle for entry in estado_entries)


def test_timeline_survives_order_edit(
    session_factory: sessionmaker[Session], order: ServiceOrder
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order.id)
        change_order_state(session, order, OrderState.EN_REPARACION, usuario="Ing. Lucio")
        session.commit()
        order.problema_reportado = "Otro problema"
        session.commit()
        assert len(order_timeline(order)) == 2


def test_void_payment_restores_balance_and_is_logged(
    session_factory: sessionmaker[Session], order: ServiceOrder
) -> None:
    """Anular un pago no lo borra: deja de contar en el saldo y queda en el historial."""
    with session_factory() as session:
        order = session.get(ServiceOrder, order.id)
        payment = register_payment(
            session, order, tipo=PaymentType.ABONO, metodo=PaymentMethod.EFECTIVO,
            monto=Decimal("50"), usuario="Ing. Lucio",
        )
        session.commit()
        assert order.saldo_pendiente == Decimal("45.00")

        void_payment(session, order, payment, usuario="Ing. Lucio", motivo="  Cobro duplicado  ")
        session.commit()

        assert order.saldo_pendiente == Decimal("95.00")
        assert payment.anulado is True
        assert payment.fecha_anulacion is not None
        assert payment.motivo_anulacion == "Cobro duplicado"
        assert len(order.payments) == 1
        assert any(event.tipo_evento == "Pago anulado" for event in order.events)


def test_voiding_a_voided_payment_is_rejected(
    session_factory: sessionmaker[Session], order: ServiceOrder
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order.id)
        payment = register_payment(
            session, order, tipo=PaymentType.ABONO, metodo=PaymentMethod.EFECTIVO,
            monto=Decimal("10"), usuario="Ing. Lucio",
        )
        void_payment(session, order, payment, usuario="Ing. Lucio")
        with pytest.raises(PaymentValidationError) as exc:
            void_payment(session, order, payment, usuario="Ing. Lucio")
        assert exc.value.errors == {"monto": "payment.already_voided"}


def test_voided_payments_do_not_allow_refunds(
    session_factory: sessionmaker[Session], order: ServiceOrder
) -> None:
    """Lo anulado deja de contar como cobrado, así que tampoco se puede reembolsar."""
    with session_factory() as session:
        order = session.get(ServiceOrder, order.id)
        payment = register_payment(
            session, order, tipo=PaymentType.ABONO, metodo=PaymentMethod.EFECTIVO,
            monto=Decimal("30"), usuario="Ing. Lucio",
        )
        void_payment(session, order, payment, usuario="Ing. Lucio")
        session.commit()
        with pytest.raises(PaymentValidationError) as exc:
            register_payment(
                session, order, tipo=PaymentType.REEMBOLSO, metodo=PaymentMethod.EFECTIVO,
                monto=Decimal("10"), usuario="Ing. Lucio",
            )
        assert exc.value.errors == {"monto": "refund.exceeds_paid"}


def test_payments_are_listed_chronologically(
    session_factory: sessionmaker[Session], order: ServiceOrder
) -> None:
    with session_factory() as session:
        order = session.get(ServiceOrder, order.id)
        register_payment(session, order, tipo=PaymentType.ABONO, metodo=PaymentMethod.EFECTIVO,
                         monto=Decimal("10"), usuario="Ing. Lucio",
                         fecha=datetime(2026, 3, 12, 10, 0))
        register_payment(session, order, tipo=PaymentType.ABONO, metodo=PaymentMethod.TARJETA,
                         monto=Decimal("5"), usuario="Ing. Lucio",
                         fecha=datetime(2026, 3, 11, 10, 0))
        session.commit()
        assert [payment.fecha for payment in payments_for_order(order)] == [
            datetime(2026, 3, 11, 10, 0),
            datetime(2026, 3, 12, 10, 0),
        ]


def test_deposit_warning_only_when_a_deposit_exists(
    session_factory: sessionmaker[Session], order: ServiceOrder
) -> None:
    """El anticipo de la recepción ya resta del saldo: registrar otro avisa sin bloquear."""
    with session_factory() as session:
        order = session.get(ServiceOrder, order.id)
        assert deposit_warning(order, PaymentType.ANTICIPO) == "deposit.already_registered"
        assert deposit_warning(order, PaymentType.ABONO) is None

        without_deposit = register_reception(
            session,
            ReceptionData(
                equipment=EquipmentData(cliente_id=None, tipo_equipo="Impresora"),
                new_customer=CustomerData(nombre_completo="Luis Paredes",
                                          telefono_principal="0999999999"),
                fecha_ingreso=ENTRY,
                costo_diagnostico=Decimal("40"),
            ),
        )
        session.commit()
        assert deposit_warning(without_deposit, PaymentType.ANTICIPO) is None
