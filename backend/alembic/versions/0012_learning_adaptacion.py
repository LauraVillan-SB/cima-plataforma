"""Learning: contador de solicitudes de actividad y señales de adaptación

Agrega lo que necesitan dos requisitos que hoy estaban a medias:

- `profile_activity_prompts`: cuántas veces se le pidió al Usuario su tipo de cultivo
  o comercio, para detenerse a las 3 solicitudes (Req 4.8, 4.9). Una fila por Perfil,
  sin PII.
- Columnas de señales en `path_progress` (Req 17.1, 17.2): repeticiones, excesos de
  tiempo, marca de simplificación y último `client_event_id` por microcápsula (para
  no contar como repetición el reintento de red de la misma petición).

Las columnas nuevas tienen valor por defecto, así que las filas existentes quedan en
"sin señales" y la migración no requiere reescribir datos.

Revision ID: 0012_learning_adaptacion
Revises: 0011_survey_sync_tablas
Create Date: 2026-11-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# identificadores de revisión usados por Alembic.
revision: str = "0012_learning_adaptacion"
down_revision: Union[str, None] = "0011_survey_sync_tablas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "profile_activity_prompts",
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("prompt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("profile_id"),
    )
    op.add_column(
        "path_progress",
        sa.Column("repeat_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "path_progress",
        sa.Column("slow_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "path_progress",
        sa.Column(
            "needs_simplification", sa.Boolean(), server_default="false", nullable=False
        ),
    )
    op.add_column(
        "path_progress",
        sa.Column(
            "finalization_events",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("path_progress", "finalization_events")
    op.drop_column("path_progress", "needs_simplification")
    op.drop_column("path_progress", "slow_count")
    op.drop_column("path_progress", "repeat_count")
    op.drop_table("profile_activity_prompts")
