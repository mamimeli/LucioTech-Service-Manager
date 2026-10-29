"""Eliminación de los dos costos fantasma de la orden (§5.3).

`costo_repuestos` y `costo_mano_obra` venían del esquema de la Fase 1: nunca se pudieron
editar desde la interfaz, siempre valían cero y el detalle real de repuestos y mano de obra
vive en `budget_lines` desde la migración 0002. Se eliminan para que la fórmula del subtotal
no pueda sumar dos veces lo mismo.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-29

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY = sa.Numeric(precision=12, scale=2)


def upgrade() -> None:
    # `ALTER TABLE ... DROP COLUMN` nativo: SQLite lo soporta desde la 3.35 y no toca las
    # claves ajenas que apuntan a `service_orders` (pagos, líneas, fotografías, historial y
    # eventos), cosa que sí haría un `batch_alter_table`, que recrea la tabla entera.
    op.drop_column("service_orders", "costo_mano_obra")
    op.drop_column("service_orders", "costo_repuestos")


def downgrade() -> None:
    op.add_column(
        "service_orders",
        sa.Column("costo_repuestos", MONEY, nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "service_orders",
        sa.Column("costo_mano_obra", MONEY, nullable=False, server_default=sa.text("0")),
    )
