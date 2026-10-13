"""Cálculo único de subtotal, impuestos, total y saldo (fórmula de §5.3).

subtotal        = costo_diagnostico + costo_repuestos + costo_mano_obra + lineas_presupuesto
impuestos       = round(subtotal * impuesto_porcentaje / 100, 2)   # 0 si los impuestos están desactivados
total           = round(subtotal - descuento + impuestos, 2)
saldo_pendiente = round(total - anticipo - pagos_realizados, 2)

Los reembolsos restan de los pagos realizados. Las líneas de presupuesto (§12) suman al subtotal.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from luciotech.database.enums import PaymentType
from luciotech.database.models import ServiceOrder
from luciotech.services.settings_service import TaxSettings

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class OrderTotals:
    subtotal: Decimal
    impuestos: Decimal
    total: Decimal
    pagos_realizados: Decimal
    saldo_pendiente: Decimal


def calculate_totals(
    *,
    costo_diagnostico: Decimal,
    costo_repuestos: Decimal,
    costo_mano_obra: Decimal,
    descuento: Decimal,
    anticipo: Decimal,
    pagos_realizados: Decimal,
    tax: TaxSettings,
    line_items_total: Decimal = ZERO,
) -> OrderTotals:
    amounts: Mapping[str, Decimal] = {
        "costo_diagnostico": costo_diagnostico,
        "costo_repuestos": costo_repuestos,
        "costo_mano_obra": costo_mano_obra,
        "descuento": descuento,
        "anticipo": anticipo,
        "line_items_total": line_items_total,
    }
    for name, value in amounts.items():
        if value < ZERO:
            raise ValueError(f"{name} no puede ser negativo.")

    subtotal = _money(costo_diagnostico + costo_repuestos + costo_mano_obra + line_items_total)
    impuestos = _money(subtotal * tax.percent / HUNDRED) if tax.enabled else ZERO
    total = _money(subtotal - descuento + impuestos)
    pagos = _money(pagos_realizados)
    saldo = _money(total - anticipo - pagos)
    return OrderTotals(
        subtotal=subtotal,
        impuestos=impuestos,
        total=total,
        pagos_realizados=pagos,
        saldo_pendiente=saldo,
    )


def net_payments(order: ServiceOrder) -> Decimal:
    total = ZERO
    for payment in order.payments:
        if payment.tipo_pago == PaymentType.REEMBOLSO.value:
            total -= payment.monto
        else:
            total += payment.monto
    return total


def recalculate_order_totals(order: ServiceOrder, tax: TaxSettings) -> OrderTotals:
    lines_sum = _money(
        sum((_money(line.cantidad * line.precio_unitario) for line in order.budget_lines), ZERO)
    )
    totals = calculate_totals(
        costo_diagnostico=_or_zero(order.costo_diagnostico),
        costo_repuestos=_or_zero(order.costo_repuestos),
        costo_mano_obra=_or_zero(order.costo_mano_obra),
        descuento=_or_zero(order.descuento),
        anticipo=_or_zero(order.anticipo),
        pagos_realizados=net_payments(order),
        tax=tax,
        line_items_total=lines_sum,
    )
    order.impuestos = totals.impuestos
    order.total = totals.total
    order.saldo_pendiente = totals.saldo_pendiente
    return totals


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _or_zero(value: Decimal | None) -> Decimal:
    return value if value is not None else ZERO
