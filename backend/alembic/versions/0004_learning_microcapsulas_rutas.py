"""Learning Service: microcapsules, learning_paths y path_progress

Crea las tablas del Learning Service (Tarea 13):
- `microcapsules`: cápsulas cortas (180–300 s) clasificadas en un tema y con
  etiquetas de actividad para la selección personalizada (Req 4.1, 4.2, 4.3).
- `learning_paths`: secuencia ordenada de microcápsulas y umbral de aprobación
  (Req 4.10, 7.3).
- `path_progress`: progreso por (profile_id, path_id), con las microcápsulas
  finalizadas y la marca de completitud (Req 4.6, 4.10). Única por titular y ruta.

Ninguna tabla contiene PII: solo identificadores internos y metadatos de contenido.

Revision ID: 0004_learning_microcapsulas_rutas
Revises: 0003_gamificacion_reconocimientos
Create Date: 2026-10-31
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# identificadores de revisión usados por Alembic.
revision: str = "0004_learning_microcapsulas_rutas"
down_revision: Union[str, None] = "0003_gamificacion_reconocimientos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- microcapsules ---
    op.create_table(
        "microcapsules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("topic", sa.String(length=32), nullable=False),
        sa.Column(
            "activity_tags",
            sa.ARRAY(sa.String(length=32)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("duration_sec", sa.Integer(), nullable=False),
        sa.Column("relevance", sa.Numeric(precision=6, scale=3), nullable=False, server_default="0"),
        sa.Column("difficulty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_microcapsules_topic"), "microcapsules", ["topic"], unique=False
    )

    # --- learning_paths ---
    op.create_table(
        "learning_paths",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "microcapsule_ids",
            sa.ARRAY(sa.Uuid()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("pass_threshold", sa.Integer(), nullable=False, server_default="70"),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- path_progress ---
    op.create_table(
        "path_progress",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("path_id", sa.Uuid(), nullable=False),
        sa.Column(
            "completed_microcapsules",
            sa.ARRAY(sa.Uuid()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_completed_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id", "path_id", name="uq_path_progress_profile_path"
        ),
    )
    op.create_index(
        op.f("ix_path_progress_profile_id"), "path_progress", ["profile_id"], unique=False
    )
    op.create_index(
        op.f("ix_path_progress_path_id"), "path_progress", ["path_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_path_progress_path_id"), table_name="path_progress")
    op.drop_index(op.f("ix_path_progress_profile_id"), table_name="path_progress")
    op.drop_table("path_progress")

    op.drop_table("learning_paths")

    op.drop_index(op.f("ix_microcapsules_topic"), table_name="microcapsules")
    op.drop_table("microcapsules")
