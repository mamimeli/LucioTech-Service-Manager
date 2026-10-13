"""Acciones sobre una orden abierta: pagos, notas, entrega y línea de tiempo (§5.6, §5.7, §9)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from luciotech.database.enums import EventType, OrderState, PaymentMethod, PaymentType
from luciotech.database.models import OrderEvent, Payment, ServiceOrder, StateHistory
from luciotech.services.settings_service import tax_settings
from luciotech.services.totals_service import net_payments, recalculate_order_totals

ZERO = Decimal("0.00")


class PaymentValidationError(ValueError):
    """Lleva un diccionario campo -> código de error para que la UI lo muestre."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Datos de pago no válidos.")
        self.errors = errors


@dataclass(frozen=True)
class TimelineEntry:
    fecha: datetime
    kind: Literal["estado", "evento"]
    titulo: str
    detalle: str
    usuario: str


def register_payment(
    session: Session,
    order: ServiceOrder,
    *,
    tipo: PaymentType | str,
    metodo: PaymentMethod | str,
    monto: Decimal,
    usuario: str,
    referencia: str | None = None,
    observaciones: str | None = None,
    fecha: datetime | None = None,
) -> Payment:
    """Registra un pago o reembolso y recalcula el saldo de la orden."""
    tipo_value = PaymentType(tipo).value
    metodo_value = PaymentMethod(metodo).value

    errors: dict[str, str] = {}
    if monto <= ZERO:
        errors["monto"] = "amount.must_be_positive"
    elif tipo_value == PaymentType.REEMBOLSO.value and monto > net_payments(order):
        errors["monto"] = "refund.exceeds_paid"
    if errors:
        raise PaymentValidationError(errors)

    payment = Payment(
        order=order,
        fecha=fecha or datetime.now(),
        tipo_pago=tipo_value,
        metodo_pago=metodo_value,
        monto=monto,
        referencia=(referencia or "").strip() or None,
        observaciones=(observaciones or "").strip() or None,
    )
    session.add(payment)
    session.flush()
    recalculate_order_totals(order, tax_settings(session))
    session.add(
        OrderEvent(
            order=order,
            tipo_evento=EventType.PAGO_RECIBIDO.value,
            titulo=f"{tipo_value} de {monto:,.2f}",
            descripcion=f"Método: {metodo_value}" + (f". Ref.: {payment.referencia}" if payment.referencia else ""),
            fecha=payment.fecha,
            usuario=usuario,
        )
    )
    session.flush()
    return payment


def payments_for_order(order: ServiceOrder) -> list[Payment]:
    """Pagos de la orden en orden cronológico, incluidos los anulados (marcados como tales)."""
    return sorted(order.payments, key=lambda payment: payment.fecha)


def deposit_warning(order: ServiceOrder, tipo: PaymentType | str) -> str | None:
    """Aviso no bloqueante antes de registrar un anticipo (§5.3).

    El anticipo capturado en la recepción vive en el campo `anticipo` de la orden y ya resta del
    saldo; un pago de tipo «Anticipo» restaría otra vez el mismo dinero.
    """
    if PaymentType(tipo).value != PaymentType.ANTICIPO.value:
        return None
    if (order.anticipo or ZERO) <= ZERO:
        return None
    return "deposit.already_registered"


def void_payment(
    session: Session,
    order: ServiceOrder,
    payment: Payment,
    *,
    usuario: str,
    motivo: str | None = None,
    when: datetime | None = None,
) -> None:
    """Anula un pago sin borrarlo: deja de contar en el saldo y queda registrado en el historial."""
    if payment.anulado:
        raise PaymentValidationError({"monto": "payment.already_voided"})
    moment = when or datetime.now()
    payment.anulado = True
    payment.fecha_anulacion = moment
    payment.motivo_anulacion = (motivo or "").strip() or None
    session.flush()
    recalculate_order_totals(order, tax_settings(session))
    session.add(
        OrderEvent(
            order=order,
            tipo_evento=EventType.PAGO_ANULADO.value,
            titulo=f"Anulado: {payment.tipo_pago} de {payment.monto:,.2f}",
            descripcion=payment.motivo_anulacion,
            fecha=moment,
            usuario=usuario,
        )
    )
    session.flush()


def add_note(
    session: Session,
    order: ServiceOrder,
    *,
    titulo: str,
    descripcion: str | None,
    usuario: str,
    tipo: EventType | str = EventType.NOTA_INTERNA,
) -> OrderEvent:
    cleaned = titulo.strip()
    if not cleaned:
        raise ValueError("El título de la nota es obligatorio.")
    event = OrderEvent(
        order=order,
        tipo_evento=EventType(tipo).value,
        titulo=cleaned,
        descripcion=(descripcion or "").strip() or None,
        fecha=datetime.now(),
        usuario=usuario,
    )
    session.add(event)
    session.flush()
    return event


def mark_delivered(
    session: Session,
    order: ServiceOrder,
    *,
    usuario: str,
    fecha_entrega: datetime | None = None,
) -> None:
    """Pasa la orden a Entregado, guarda la fecha de entrega y lo registra en la línea de tiempo."""
    when = fecha_entrega or datetime.now()
    previous = order.estado
    order.estado = OrderState.ENTREGADO.value
    order.fecha_entrega = when
    session.add(
        StateHistory(
            order=order,
            estado_anterior=previous,
            estado_nuevo=OrderState.ENTREGADO.value,
            comentario="Equipo entregado al cliente",
            fecha=when,
            usuario=usuario,
        )
    )
    session.add(
        OrderEvent(
            order=order,
            tipo_evento=EventType.EQUIPO_ENTREGADO.value,
            titulo="Equipo entregado",
            descripcion=None,
            fecha=when,
            usuario=usuario,
        )
    )
    session.flush()


def order_timeline(order: ServiceOrder) -> list[TimelineEntry]:
    """Cambios de estado y notas en orden cronológico. Nunca se borran al editar la orden."""
    entries: list[TimelineEntry] = []
    for change in order.state_changes:
        previous = change.estado_anterior or "—"
        detail = f"{previous} → {change.estado_nuevo}"
        if change.comentario:
            detail += f". {change.comentario}"
        entries.append(
            TimelineEntry(change.fecha, "estado", "Cambio de estado", detail, change.usuario)
        )
    for event in order.events:
        entries.append(
            TimelineEntry(event.fecha, "evento", event.titulo, event.descripcion or "", event.usuario)
        )
    return sorted(entries, key=lambda entry: entry.fecha)
