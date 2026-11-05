"""Assessment Service: assessments y assessment_attempts

Crea las tablas del Assessment Service (Tarea 14):
- `assessments`: evaluación por ruta (única por `path_id`), con las preguntas y
  su clave de respuestas en JSONB y el umbral de aprobación (Req 7.1, 7.3, 7.6).
- `assessment_attempts`: intentos por (profile_id, path_id), con puntaje 0–100,
  resultado, número de intento y ventana de enfriamiento de 24 h (Req 7.2–7.5).

Ninguna tabla contiene PII: solo identificadores internos, la definición de la
evaluación y resultados numéricos.

Revision ID: 0005_assessment_evaluaciones
Revises: 0004_learning_microcapsulas_rutas
Create Date: 2026-10-31
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# identificadores de revisión usados por Alembic.
revision: str = "0005_assessment_evaluaciones"
down_revision: Union[str, None] = "0004_learning_microcapsulas_rutas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- assessments ---
    op.create_table(
        "assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("path_id", sa.Uuid(), nullable=False),
        sa.Column(
            "questions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("pass_threshold", sa.Integer(), nullable=False, server_default="70"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_assessments_path_id"), "assessments", ["path_id"], unique=True
    )

    # --- assessment_attempts ---
    op.create_table(
        "assessment_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("path_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_assessment_attempts_profile_id"),
        "assessment_attempts",
        ["profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assessment_attempts_path_id"),
        "assessment_attempts",
        ["path_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_assessment_attempts_path_id"), table_name="assessment_attempts"
    )
    op.drop_index(
        op.f("ix_assessment_attempts_profile_id"), table_name="assessment_attempts"
    )
    op.drop_table("assessment_attempts")

    op.drop_index(op.f("ix_assessments_path_id"), table_name="assessments")
    op.drop_table("assessments")
