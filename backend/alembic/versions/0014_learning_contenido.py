"""Learning: contenido de las microcápsulas y video de apoyo opcional

Hasta ahora una microcápsula solo tenía tema, duración y etiquetas: no había nada que
mostrarle al Usuario. Esta migración agrega el contenido (título, resumen, párrafos y
puntos clave, todo texto plano) y un video de apoyo opcional de YouTube, guardado solo
como identificador de 11 caracteres más título y canal para dar crédito.

Todas las columnas son opcionales o tienen valor por defecto, así que las cápsulas
existentes siguen siendo válidas y la migración no reescribe datos.

Revision ID: 0014_learning_contenido
Revises: 0013_learning_event_outbox
Create Date: 2026-11-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# identificadores de revisión usados por Alembic.
revision: str = "0014_learning_contenido"
down_revision: Union[str, None] = "0013_learning_event_outbox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("microcapsules", sa.Column("title", sa.String(length=120), nullable=True))
    op.add_column("microcapsules", sa.Column("summary", sa.String(length=280), nullable=True))
    op.add_column(
        "microcapsules",
        sa.Column(
            "paragraphs",
            postgresql.ARRAY(sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    op.add_column(
        "microcapsules",
        sa.Column(
            "key_points",
            postgresql.ARRAY(sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    op.add_column("microcapsules", sa.Column("video_id", sa.String(length=11), nullable=True))
    op.add_column(
        "microcapsules", sa.Column("video_title", sa.String(length=200), nullable=True)
    )
    op.add_column(
        "microcapsules", sa.Column("video_channel", sa.String(length=100), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("microcapsules", "video_channel")
    op.drop_column("microcapsules", "video_title")
    op.drop_column("microcapsules", "video_id")
    op.drop_column("microcapsules", "key_points")
    op.drop_column("microcapsules", "paragraphs")
    op.drop_column("microcapsules", "summary")
    op.drop_column("microcapsules", "title")
