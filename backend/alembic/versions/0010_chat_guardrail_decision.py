"""Conversational Agent Service: columna guardrail_decision

Añade la columna `guardrail_decision` a `ai_interactions` (Tarea 11.5): registra
de forma auditable la decisión del guardrail aplicada a la interacción
(permitido | bloqueo_entrada | salida_no_validada | derivado_humano |
kill_switch), sin PII (Req 16.4). Nula hasta que se procesa la interacción.

Revision ID: 0010_chat_guardrail_decision
Revises: 0009_chat_response_audio_ref
Create Date: 2026-10-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# identificadores de revisión usados por Alembic.
revision: str = "0010_chat_guardrail_decision"
down_revision: Union[str, None] = "0009_chat_response_audio_ref"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_interactions",
        sa.Column("guardrail_decision", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_interactions", "guardrail_decision")
