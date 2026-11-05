"""Conversational Agent Service: chat_messages y ai_interactions

Crea las tablas del Conversational Agent Service (Tarea 11.3):
- `chat_messages`: mensaje del Usuario y ciclo de vida de su inferencia
  asíncrona (pendiente/procesando/listo/fallido), idempotente por
  `client_event_id`. Guarda solo la entrada redactada (sin PII) y la respuesta.
- `ai_interactions`: registro auditable de la interacción con el modelo (entrada
  redactada, salida, versión del modelo, decisión del guardrail, confianza STT),
  correlacionado por `correlation_id`. Sin PII (Req 3.9, 16.4).

Revision ID: 0008_chat_inferencia
Revises: 0007_conversion_incentivos
Create Date: 2026-11-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# identificadores de revisión usados por Alembic.
revision: str = "0008_chat_inferencia"
down_revision: Union[str, None] = "0007_conversion_incentivos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- chat_messages ---
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_event_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("redacted_input", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(length=16), server_default="pendiente", nullable=False
        ),
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
        op.f("ix_chat_messages_client_event_id"),
        "chat_messages",
        ["client_event_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_chat_messages_profile_id"), "chat_messages", ["profile_id"], unique=False
    )
    op.create_index(
        op.f("ix_chat_messages_status"), "chat_messages", ["status"], unique=False
    )

    # --- ai_interactions ---
    op.create_table(
        "ai_interactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("redacted_input", sa.Text(), nullable=False),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("guardrail_decision", sa.String(length=32), nullable=True),
        sa.Column("stt_confidence", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ai_interactions_correlation_id"),
        "ai_interactions",
        ["correlation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_interactions_message_id"),
        "ai_interactions",
        ["message_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_interactions_message_id"), table_name="ai_interactions")
    op.drop_index(
        op.f("ix_ai_interactions_correlation_id"), table_name="ai_interactions"
    )
    op.drop_table("ai_interactions")

    op.drop_index(op.f("ix_chat_messages_status"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_profile_id"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_client_event_id"), table_name="chat_messages")
    op.drop_table("chat_messages")
