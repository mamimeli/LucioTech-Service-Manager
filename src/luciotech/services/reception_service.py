"""Recepción de equipos: cliente, equipo y orden en una sola transacción (§7 del ROADMAP)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from luciotech.config import DEFAULT_USER
from luciotech.database.enums import Priority
from luciotech.database.models import Customer, Equipment, ServiceOrder
from luciotech.services.customer_service import (
    CustomerData,
    customer_input_errors,
    find_possible_duplicates,
    save_customer,
)
from luciotech.services.equipment_service import (
    EquipmentData,
    equipment_input_errors,
    find_orders_with_serial,
    save_equipment,
)
from luciotech.services.order_service import create_service_order
from luciotech.services.settings_service import equipment_types, tax_settings
from luciotech.services.totals_service import calculate_totals

ZERO = Decimal("0.00")


class ReceptionValidationError(ValueError):
    """Lleva un diccionario campo -> código de error para que la UI lo muestre."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Datos de recepción no válidos.")
        self.errors = errors


@dataclass(frozen=True)
class ReceptionData:
    equipment: EquipmentData
    customer_id: int | None = None
    new_customer: CustomerData | None = None
    equipment_id: int | None = None
    fecha_ingreso: datetime | None = None
    fecha_estimada_entrega: datetime | None = None
    prioridad: Priority | str = Priority.NORMAL
    tecnico_responsable: str | None = None
    costo_diagnostico: Decimal = ZERO
    anticipo: Decimal = ZERO
    usuario: str = DEFAULT_USER


@dataclass(frozen=True)
class ReceptionWarnings:
    """Advertencias no bloqueantes: clientes parecidos y órdenes con el mismo número de serie."""

    duplicate_customers: list[Customer]
    serial_orders: list[ServiceOrder]

    @property
    def has_any(self) -> bool:
        return bool(self.duplicate_customers or self.serial_orders)


def reception_input_errors(session: Session, data: ReceptionData) -> dict[str, str]:
    errors: dict[str, str] = {}
    if (data.customer_id is None) == (data.new_customer is None):
        errors["cliente"] = "customer.required"
    elif data.customer_id is not None and session.get(Customer, data.customer_id) is None:
        errors["cliente"] = "not_found"
    if data.new_customer is not None:
        errors.update(customer_input_errors(data.new_customer))

    if data.equipment_id is not None:
        existing = session.get(Equipment, data.equipment_id)
        if existing is None:
            errors["equipo"] = "not_found"
        elif data.customer_id is not None and existing.cliente_id != data.customer_id:
            errors["equipo"] = "equipment.other_customer"
        elif data.new_customer is not None:
            errors["equipo"] = "equipment.other_customer"

    equipment_errors = equipment_input_errors(data.equipment, equipment_types(session))
    errors.update({field: code for field, code in equipment_errors.items() if field != "cliente_id"})

    errors.update(_amount_errors(session, data))

    ingreso = data.fecha_ingreso or datetime.now()
    if data.fecha_estimada_entrega is not None and data.fecha_estimada_entrega < ingreso:
        errors["fecha_estimada_entrega"] = "date.before_entry"
    return errors


def reception_warnings(session: Session, data: ReceptionData) -> ReceptionWarnings:
    duplicates: list[Customer] = []
    if data.new_customer is not None:
        duplicates = find_possible_duplicates(
            session,
            data.new_customer.numero_identificacion,
            data.new_customer.telefono_principal,
        )
    serial_orders = find_orders_with_serial(session, data.equipment.numero_serie)
    return ReceptionWarnings(duplicate_customers=duplicates, serial_orders=serial_orders)


def register_reception(session: Session, data: ReceptionData) -> ServiceOrder:
    """Guarda cliente (si es nuevo), equipo y orden. El llamador decide el commit."""
    errors = reception_input_errors(session, data)
    if errors:
        raise ReceptionValidationError(errors)

    customer = _resolve_customer(session, data)
    if data.equipment_id is not None:
        equipment = session.get(Equipment, data.equipment_id)
    else:
        equipment = save_equipment(
            session,
            replace(data.equipment, cliente_id=customer.id),
            equipment_types(session),
        )
    return create_service_order(
        session,
        customer=customer,
        equipment=equipment,
        usuario=data.usuario,
        prioridad=data.prioridad,
        fecha_ingreso=data.fecha_ingreso or datetime.now(),
        fecha_estimada_entrega=data.fecha_estimada_entrega,
        costo_diagnostico=data.costo_diagnostico,
        anticipo=data.anticipo,
        tecnico_responsable=data.tecnico_responsable or data.usuario,
        problema_reportado=data.equipment.problema_reportado_cliente,
    )


def _resolve_customer(session: Session, data: ReceptionData) -> Customer:
    if data.new_customer is not None:
        return save_customer(session, data.new_customer)
    customer = session.get(Customer, data.customer_id)
    if customer is None:
        raise ValueError("Cliente no encontrado.")
    return customer


def _amount_errors(session: Session, data: ReceptionData) -> dict[str, str]:
    errors: dict[str, str] = {}
    for field, amount in (
        ("costo_diagnostico", data.costo_diagnostico),
        ("anticipo", data.anticipo),
    ):
        if amount < ZERO:
            errors[field] = "amount.negative"
    if errors:
        return errors

    total = calculate_totals(
        costo_diagnostico=data.costo_diagnostico,
        descuento=ZERO,
        anticipo=ZERO,
        pagos_realizados=ZERO,
        tax=tax_settings(session),
    ).total
    if data.anticipo > total:
        errors["anticipo"] = "anticipo.exceeds_total"
    return errors
