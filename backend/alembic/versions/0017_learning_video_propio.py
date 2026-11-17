"""Learning: video propio opcional de la microcápsula

Hasta ahora el único video de apoyo era de YouTube. Se agrega `video_file`, el nombre
de un archivo `.mp4` en la carpeta de medios del backend (solo el nombre, validado con
`MEDIA_FILE_PATTERN`; nunca una ruta ni una URL). Es opcional y la migración no
reescribe datos.

Revision ID: 0017_learning_video_propio
Revises: 0016_learning_rutas_titulo
Create Date: 2026-11-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# identificadores de revisión usados por Alembic.
revision: str = "0017_learning_video_propio"
down_revision: Union[str, None] = "0016_learning_rutas_titulo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("microcapsules", sa.Column("video_file", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("microcapsules", "video_file")
