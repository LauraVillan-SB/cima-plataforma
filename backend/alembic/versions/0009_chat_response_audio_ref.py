"""Conversational Agent Service: columna response_audio_ref

Añade la columna `response_audio_ref` a `ai_interactions` (Tarea 11.4): guarda la
referencia al audio TTS de la respuesta (no el binario), para el canal de voz
(Req 14.3). Nula cuando no hay audio o el canal fue solo texto.

Revision ID: 0009_chat_response_audio_ref
Revises: 0008_chat_ai_interactions
Create Date: 2026-10-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# identificadores de revisión usados por Alembic.
revision: str = "0009_chat_response_audio_ref"
down_revision: Union[str, None] = "0008_chat_ai_interactions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_interactions",
        sa.Column("response_audio_ref", sa.String(length=256), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_interactions", "response_audio_ref")
