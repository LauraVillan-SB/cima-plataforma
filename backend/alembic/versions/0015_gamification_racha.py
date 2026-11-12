"""Gamification: racha diaria de actividad

Agrega a `user_points` la racha actual (días consecutivos con actividad) y la fecha
del último día que contó. Con eso el backend calcula "N días en racha" sin guardar
nada personal: solo un entero y una fecha por Perfil.

Las columnas tienen valor por defecto, así que las filas existentes quedan con racha
0 y sin fecha, y la migración no reescribe datos.

Revision ID: 0015_gamification_racha
Revises: 0014_learning_contenido
Create Date: 2026-11-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# identificadores de revisión usados por Alembic.
revision: str = "0015_gamification_racha"
down_revision: Union[str, None] = "0014_learning_contenido"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_points",
        sa.Column("current_streak", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "user_points",
        sa.Column("last_activity_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_points", "last_activity_date")
    op.drop_column("user_points", "current_streak")
