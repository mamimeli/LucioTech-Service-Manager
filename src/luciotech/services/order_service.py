"""Creación y borrado lógico de órdenes de servicio (§5.3, §7.3 y §18)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from luciotech.database.enums import EventType, OrderState, Priority
from luciotech.database.models import (
    Customer,
    Equipment,
    OrderEvent,
    ServiceOrder,
    StateHistory,
)
from luciotech.services import settings_service
from luciotech.services.order_number_service import next_order_number
from luciotech.services.totals_service import recalculate_order_totals

ZERO = Decimal("0.00")


def create_service_order(
    session: Session,
    *,
    customer: Customer,
    equipment: Equipment,
    usuario: str,
    prioridad: Priority | str = Priority.NORMAL,
    fecha_ingreso: datetime | None = None,
    fecha_estimada_entrega: datetime | None = None,
    costo_diagnostico: Decimal = ZERO,
    anticipo: Decimal = ZERO,
    tecnico_responsable: str | None = None,
    problema_reportado: str | None = None,
) -> ServiceOrder:
    if equipment.customer is not customer:
        raise ValueError("El equipo no pertenece al cliente indicado.")

    ingreso = fecha_ingreso or datetime.now()
    if fecha_estimada_entrega is not None and fecha_estimada_entrega < ingreso:
        raise ValueError("La fecha estimada de entrega no puede ser anterior a la fecha de ingreso.")

    order = ServiceOrder(
        numero_orden=next_order_number(session, ingreso.year),
        customer=customer,
        equipment=equipment,
        fecha_ingreso=ingreso,
        fecha_estimada_entrega=fecha_estimada_entrega,
        estado=OrderState.RECIBIDO.value,
        prioridad=Priority(prioridad).value,
        tecnico_responsable=tecnico_responsable,
        problema_reportado=problema_reportado,
        costo_diagnostico=costo_diagnostico,
        costo_repuestos=ZERO,
        costo_mano_obra=ZERO,
        descuento=ZERO,
        anticipo=anticipo,
        garantia_dias=0,
        activo=True,
    )
    session.add(order)
    session.flush()

    session.add(
        StateHistory(
            order=order,
            estado_anterior=None,
            estado_nuevo=OrderState.RECIBIDO.value,
            comentario="Orden creada",
            fecha=ingreso,
            usuario=usuario,
        )
    )
    recalculate_order_totals(order, settings_service.tax_settings(session))
    session.flush()
    return order


def soft_delete_order(
    session: Session,
    order: ServiceOrder,
    when: datetime | None = None,
    *,
    usuario: str | None = None,
    motivo: str | None = None,
) -> None:
    """Oculta la orden sin borrarla; su estado no cambia (§18).

    La orden nunca se borra de la base: solo deja de aparecer en la lista y pasa a la papelera,
    desde donde puede restaurarse. Si se indica `usuario`, el movimiento queda en el historial.
    """
    moment = when or datetime.now()
    order.activo = False
    order.fecha_eliminacion = moment
    if usuario:
        session.add(
            OrderEvent(
                order=order,
                tipo_evento=EventType.ORDEN_ELIMINADA.value,
                titulo="Orden enviada a la papelera",
                descripcion=(motivo or "").strip() or None,
                fecha=moment,
                usuario=usuario,
            )
        )
    session.flush()


def restore_order(
    session: Session,
    order: ServiceOrder,
    *,
    usuario: str | None = None,
) -> None:
    """Devuelve la orden desde la papelera a la lista activa (§18)."""
    order.activo = True
    order.fecha_eliminacion = None
    if usuario:
        session.add(
            OrderEvent(
                order=order,
                tipo_evento=EventType.ORDEN_RESTAURADA.value,
                titulo="Orden restaurada desde la papelera",
                descripcion=None,
                fecha=datetime.now(),
                usuario=usuario,
            )
        )
    session.flush()
