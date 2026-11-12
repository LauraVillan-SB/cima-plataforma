"""Learning: título y resumen de las rutas de aprendizaje

Una ruta solo tenía la lista de microcápsulas y el umbral de aprobación, así que no se
podía mostrar con un nombre. Se agregan `title` y `summary` (texto plano, opcionales).
Las filas existentes quedan sin título y la migración no reescribe datos.

Revision ID: 0016_learning_rutas_titulo
Revises: 0015_gamification_racha
Create Date: 2026-11-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# identificadores de revisión usados por Alembic.
revision: str = "0016_learning_rutas_titulo"
down_revision: Union[str, None] = "0015_gamification_racha"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("learning_paths", sa.Column("title", sa.String(length=120), nullable=True))
    op.add_column("learning_paths", sa.Column("summary", sa.String(length=280), nullable=True))


def downgrade() -> None:
    op.drop_column("learning_paths", "summary")
    op.drop_column("learning_paths", "title")
