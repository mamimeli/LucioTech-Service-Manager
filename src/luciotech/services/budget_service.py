"""Líneas de presupuesto de una orden (§12): alta, edición y baja.

Cada línea tiene tipo (§12), descripción, cantidad y precio unitario; el subtotal de la
línea se calcula en vez de guardarse. El subtotal, impuestos, total y saldo de la orden
se recalculan siempre con totals_service (§5.3), que ya suma las líneas.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from luciotech.database.enums import BudgetLineType
from luciotech.database.models import BudgetLine, ServiceOrder
from luciotech.services.settings_service import tax_settings
from luciotech.services.totals_service import recalculate_order_totals

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


class BudgetLineValidationError(ValueError):
    """Lleva un diccionario campo -> código de error para que la UI lo muestre."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Línea de presupuesto no válida.")
        self.errors = errors


def line_subtotal(line: BudgetLine) -> Decimal:
    return _money(line.cantidad * line.precio_unitario)


def lines_for_order(session: Session, order_id: int) -> list[BudgetLine]:
    statement = select(BudgetLine).where(BudgetLine.orden_id == order_id).order_by(BudgetLine.id)
    return list(session.scalars(statement))


def add_line(
    session: Session,
    order: ServiceOrder,
    *,
    tipo: BudgetLineType | str,
    descripcion: str,
    cantidad: Decimal,
    precio_unitario: Decimal,
) -> BudgetLine:
    tipo_value, text, quantity, price = _validate(tipo, descripcion, cantidad, precio_unitario)
    line = BudgetLine(
        order=order,
        tipo_linea=tipo_value,
        descripcion=text,
        cantidad=quantity,
        precio_unitario=price,
    )
    session.add(line)
    session.flush()
    _recalculate(session, order)
    return line


def update_line(
    session: Session,
    line: BudgetLine,
    *,
    tipo: BudgetLineType | str | None = None,
    descripcion: str | None = None,
    cantidad: Decimal | None = None,
    precio_unitario: Decimal | None = None,
) -> BudgetLine:
    """Actualiza una línea; los argumentos None dejan el valor actual."""
    tipo_value, text, quantity, price = _validate(
        line.tipo_linea if tipo is None else tipo,
        line.descripcion if descripcion is None else descripcion,
        line.cantidad if cantidad is None else cantidad,
        line.precio_unitario if precio_unitario is None else precio_unitario,
    )
    line.tipo_linea = tipo_value
    line.descripcion = text
    line.cantidad = quantity
    line.precio_unitario = price
    session.flush()
    _recalculate(session, line.order)
    return line


def remove_line(session: Session, line: BudgetLine) -> None:
    order = line.order
    order.budget_lines.remove(line)
    session.flush()
    _recalculate(session, order)


def set_discount(session: Session, order: ServiceOrder, descuento: Decimal) -> None:
    """Fija el descuento de la orden (§12) y recalcula los totales."""
    value = _money(descuento)
    if value < ZERO:
        raise BudgetLineValidationError({"descuento": "amount.negative"})
    order.descuento = value
    _recalculate(session, order)


def _validate(
    tipo: BudgetLineType | str,
    descripcion: str,
    cantidad: Decimal,
    precio_unitario: Decimal,
) -> tuple[str, str, Decimal, Decimal]:
    errors: dict[str, str] = {}
    try:
        tipo_value = BudgetLineType(tipo).value
    except ValueError:
        errors["tipo_linea"] = "invalid_type"
    text = (descripcion or "").strip()
    if not text:
        errors["descripcion"] = "required"
    if cantidad is None or cantidad <= ZERO:
        errors["cantidad"] = "amount.must_be_positive"
    if precio_unitario is None or precio_unitario < ZERO:
        errors["precio_unitario"] = "amount.negative"
    if errors:
        raise BudgetLineValidationError(errors)
    return tipo_value, text, _money(cantidad), _money(precio_unitario)


def _recalculate(session: Session, order: ServiceOrder) -> None:
    recalculate_order_totals(order, tax_settings(session))
    session.flush()


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)
