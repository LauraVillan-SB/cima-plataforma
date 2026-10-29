"""Esquema inicial: profiles y metric_events (+ extensión PgVector)

Crea las tablas de los dominios ya implementados en `develop`:
- `profiles` (Profile Service / Auth): datos mínimos del Usuario, hash de la
  Clave, rol y campos de bloqueo por intentos (Req 1.5, 1.12, 1.13, 9.1, 15.5).
- `metric_events` (Metrics Service): eventos por zona, idempotentes por
  `client_event_id` (Req 8.1, 8.2, 8.4).

Habilita la extensión `vector` (PgVector) para la recuperación por similitud de
futuras entidades (Req 17.4), sin crear aún columnas vectoriales.

Revision ID: 0001_esquema_inicial
Revises:
Create Date: 2026-10-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# identificadores de revisión usados por Alembic.
revision: str = "0001_esquema_inicial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensión PgVector para búsquedas por similitud (Req 17.4).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- profiles (Profile Service / Auth) ---
    op.create_table(
        "profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("phone_e164", sa.String(length=16), nullable=False),
        sa.Column("clave_hash", sa.String(length=128), nullable=False),
        sa.Column("activity_type", sa.String(length=32), nullable=False),
        sa.Column("geo_zone", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default="usuario"),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_profiles_phone_e164"), "profiles", ["phone_e164"], unique=True
    )

    # --- metric_events (Metrics Service) ---
    op.create_table(
        "metric_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_event_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("geo_zone", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("classified", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_metric_events_client_event_id"),
        "metric_events",
        ["client_event_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_metric_events_profile_id"), "metric_events", ["profile_id"], unique=False
    )
    op.create_index(
        op.f("ix_metric_events_geo_zone"), "metric_events", ["geo_zone"], unique=False
    )
    op.create_index(
        op.f("ix_metric_events_event_type"), "metric_events", ["event_type"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_metric_events_event_type"), table_name="metric_events")
    op.drop_index(op.f("ix_metric_events_geo_zone"), table_name="metric_events")
    op.drop_index(op.f("ix_metric_events_profile_id"), table_name="metric_events")
    op.drop_index(op.f("ix_metric_events_client_event_id"), table_name="metric_events")
    op.drop_table("metric_events")

    op.drop_index(op.f("ix_profiles_phone_e164"), table_name="profiles")
    op.drop_table("profiles")
