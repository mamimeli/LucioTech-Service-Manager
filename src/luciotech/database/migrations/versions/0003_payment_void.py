"""Anulación de pagos: columnas anulado, fecha_anulacion y motivo_anulacion (§5.7).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-13

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("anulado", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("payments", sa.Column("fecha_anulacion", sa.DateTime(), nullable=True))
    op.add_column("payments", sa.Column("motivo_anulacion", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "motivo_anulacion")
    op.drop_column("payments", "fecha_anulacion")
    op.drop_column("payments", "anulado")
