"""Learning: cola de eventos pendientes de registro (Req 4.7, 8.4)

Crea `learning_event_outbox`, donde el Learning Service conserva un evento de
`microcapsula_completada` o `ruta_completada` cuando su registro en Metrics sigue
fallando tras los reintentos acotados, para registrarlo después sin pérdida de datos.
`client_event_id` es único (idempotencia) y la tabla solo guarda identificadores y el
tipo de evento, sin PII.

Revision ID: 0013_learning_event_outbox
Revises: 0012_learning_adaptacion
Create Date: 2026-11-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# identificadores de revisión usados por Alembic.
revision: str = "0013_learning_event_outbox"
down_revision: Union[str, None] = "0012_learning_adaptacion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learning_event_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_event_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_event_id"),
    )
    op.create_index(
        op.f("ix_learning_event_outbox_profile_id"),
        "learning_event_outbox",
        ["profile_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_learning_event_outbox_profile_id"), table_name="learning_event_outbox"
    )
    op.drop_table("learning_event_outbox")
