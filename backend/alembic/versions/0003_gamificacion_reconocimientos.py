"""Gamification Service: user_badges y user_points

Crea las tablas del Gamification Service (Tarea 17.1):
- `user_badges`: Insignias otorgadas a un Perfil. Única por (profile_id,
  badge_code) para no duplicar (Req 19.5) e idempotente por `client_event_id`
  (Req 19.6).
- `user_points`: total de puntos por Perfil, una fila por `profile_id` (Req 19.2).

Ninguna tabla contiene PII: solo identificadores internos y códigos.

Revision ID: 0003_gamificacion_reconocimientos
Revises: 0002_conversion_microseguros
Create Date: 2026-10-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# identificadores de revisión usados por Alembic.
revision: str = "0003_gamificacion_reconocimientos"
down_revision: Union[str, None] = "0002_conversion_microseguros"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- user_badges ---
    op.create_table(
        "user_badges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("badge_code", sa.String(length=64), nullable=False),
        sa.Column("client_event_id", sa.Uuid(), nullable=False),
        sa.Column(
            "awarded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id", "badge_code", name="uq_user_badge_profile_badge"
        ),
    )
    op.create_index(
        op.f("ix_user_badges_client_event_id"),
        "user_badges",
        ["client_event_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_user_badges_profile_id"), "user_badges", ["profile_id"], unique=False
    )

    # --- user_points ---
    op.create_table(
        "user_points",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("total_points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_points_profile_id"), "user_points", ["profile_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_points_profile_id"), table_name="user_points")
    op.drop_table("user_points")

    op.drop_index(op.f("ix_user_badges_profile_id"), table_name="user_badges")
    op.drop_index(op.f("ix_user_badges_client_event_id"), table_name="user_badges")
    op.drop_table("user_badges")
