"""Conversational Agent Service: ai_interactions

Crea la tabla del Conversational Agent Service (Tarea 11.3):
- `ai_interactions`: mensaje del Usuario y resultado de la inferencia asíncrona.
  El contenido se guarda ya redactado (sin PII, Req 3.9). Estado del ciclo de
  vida: encolado | procesando | listo | error (Req 3.5-3.8).

Revision ID: 0008_chat_ai_interactions
Revises: 0007_conversion_incentivos
Create Date: 2026-10-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# identificadores de revisión usados por Alembic.
revision: str = "0008_chat_ai_interactions"
down_revision: Union[str, None] = "0007_conversion_incentivos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_interactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("input_redacted", sa.Text(), nullable=False),
        sa.Column("input_channel", sa.String(length=8), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="encolado",
        ),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ai_interactions_profile_id"),
        "ai_interactions",
        ["profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_interactions_status"),
        "ai_interactions",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_interactions_status"), table_name="ai_interactions")
    op.drop_index(op.f("ix_ai_interactions_profile_id"), table_name="ai_interactions")
    op.drop_table("ai_interactions")
