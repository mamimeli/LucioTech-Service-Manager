"""Consulta de órdenes con filtros básicos para la lista (§10 del ROADMAP, alcance Fase 1)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from luciotech.database.models import Customer, Equipment, ServiceOrder


@dataclass(frozen=True)
class OrderFilter:
    text: str = ""
    estado: str | None = None
    prioridad: str | None = None
    tipo_equipo: str | None = None
    solo_con_saldo: bool = False
    incluir_eliminadas: bool = False
    solo_eliminadas: bool = False


def search_orders(session: Session, flt: OrderFilter) -> list[ServiceOrder]:
    statement = select(ServiceOrder).join(ServiceOrder.customer).join(ServiceOrder.equipment)

    if flt.solo_eliminadas:
        statement = statement.where(ServiceOrder.activo.is_(False))
    elif not flt.incluir_eliminadas:
        statement = statement.where(ServiceOrder.activo.is_(True))

    text = flt.text.strip()
    if text:
        statement = statement.where(
            or_(
                ServiceOrder.numero_orden.icontains(text, autoescape=True),
                Customer.nombre_completo.icontains(text, autoescape=True),
                Customer.telefono_principal.icontains(text, autoescape=True),
                Equipment.numero_serie.icontains(text, autoescape=True),
                Equipment.marca.icontains(text, autoescape=True),
                Equipment.modelo.icontains(text, autoescape=True),
            )
        )
    if flt.estado:
        statement = statement.where(ServiceOrder.estado == flt.estado)
    if flt.prioridad:
        statement = statement.where(ServiceOrder.prioridad == flt.prioridad)
    if flt.tipo_equipo:
        statement = statement.where(Equipment.tipo_equipo == flt.tipo_equipo)
    if flt.solo_con_saldo:
        statement = statement.where(ServiceOrder.saldo_pendiente > 0)

    statement = statement.order_by(ServiceOrder.fecha_ingreso.desc(), ServiceOrder.id.desc())
    return list(session.scalars(statement))
