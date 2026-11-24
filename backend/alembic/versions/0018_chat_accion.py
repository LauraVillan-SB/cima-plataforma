"""Chat: acción propuesta por el asistente

Se agrega `action` (JSON, opcional) a `ai_interactions`: la acción que el asistente
propuso y el servidor resolvió contra la allowlist (continuar una ruta, ir a una
pantalla o proponer un cambio de perfil). No guarda PII ni texto del modelo. La
migración no reescribe datos.

Revision ID: 0018_chat_accion
Revises: 0017_learning_video_propio
Create Date: 2026-11-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# identificadores de revisión usados por Alembic.
revision: str = "0018_chat_accion"
down_revision: Union[str, None] = "0017_learning_video_propio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_interactions", sa.Column("action", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_interactions", "action")
