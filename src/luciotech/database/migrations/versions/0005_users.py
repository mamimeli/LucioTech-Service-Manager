"""Tabla de usuarios de la aplicación (§19).

El §19 pedía, para la primera versión, no crear tablas de usuarios y dejar solo el terreno
preparado. Esa primera versión ya está cerrada y el taller necesita que cada técnico entre con
su propia cuenta: esta migración crea `usuarios` con el nombre de acceso, el nombre visible, el
hash de la contraseña y el rol.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-01

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre_usuario", sa.String(length=60), nullable=False),
        sa.Column("nombre_completo", sa.String(length=120), nullable=False),
        sa.Column("contrasena_hash", sa.String(length=255), nullable=False),
        sa.Column("rol", sa.String(length=20), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("fecha_creacion", sa.DateTime(), nullable=False),
        sa.Column("ultimo_acceso", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_usuarios_nombre_usuario", "usuarios", ["nombre_usuario"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_usuarios_nombre_usuario", table_name="usuarios")
    op.drop_table("usuarios")
