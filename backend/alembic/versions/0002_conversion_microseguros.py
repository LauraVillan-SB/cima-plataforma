"""Conversion Service: conversion_intents y no_offer_events

Crea las tablas del Conversion Service (Tarea 16.2):
- `conversion_intents`: intención del Usuario de adquirir un Microseguro,
  idempotente por `client_event_id` y única por (profile_id, path_id,
  option_code). CIMA no emite pólizas ni cobra; solo registra el interés
  (Req 5.5, 5.6).
- `no_offer_events`: ausencia de oferta para un tipo de actividad, sin PII, para
  análisis posterior (Req 5.8).

Revision ID: 0002_conversion_microseguros
Revises: 0001_esquema_inicial
Create Date: 2026-10-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# identificadores de revisión usados por Alembic.
revision: str = "0002_conversion_microseguros"
down_revision: Union[str, None] = "0001_esquema_inicial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- conversion_intents ---
    op.create_table(
        "conversion_intents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("path_id", sa.Uuid(), nullable=False),
        sa.Column("option_code", sa.String(length=64), nullable=False),
        sa.Column("client_event_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id",
            "path_id",
            "option_code",
            name="uq_conversion_intent_profile_path_option",
        ),
    )
    op.create_index(
        op.f("ix_conversion_intents_client_event_id"),
        "conversion_intents",
        ["client_event_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_conversion_intents_profile_id"),
        "conversion_intents",
        ["profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversion_intents_path_id"),
        "conversion_intents",
        ["path_id"],
        unique=False,
    )

    # --- no_offer_events ---
    op.create_table(
        "no_offer_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("activity_type", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_no_offer_events_activity_type"),
        "no_offer_events",
        ["activity_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_no_offer_events_activity_type"), table_name="no_offer_events")
    op.drop_table("no_offer_events")

    op.drop_index(
        op.f("ix_conversion_intents_path_id"), table_name="conversion_intents"
    )
    op.drop_index(
        op.f("ix_conversion_intents_profile_id"), table_name="conversion_intents"
    )
    op.drop_index(
        op.f("ix_conversion_intents_client_event_id"), table_name="conversion_intents"
    )
    op.drop_table("conversion_intents")
