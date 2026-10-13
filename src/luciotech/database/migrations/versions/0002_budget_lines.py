"""Líneas de presupuesto: tabla budget_lines (§12).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-12

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "budget_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("orden_id", sa.Integer(), nullable=False),
        sa.Column("tipo_linea", sa.String(length=40), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("cantidad", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("fecha_creacion", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["orden_id"], ["service_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_budget_lines_orden_id"), "budget_lines", ["orden_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_budget_lines_orden_id"), table_name="budget_lines")
    op.drop_table("budget_lines")
