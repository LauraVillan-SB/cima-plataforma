"""Survey y Sync: surveys, survey_responses, sync_actions y sync_path_progress

Los modelos de estos dos servicios existían en el código pero no tenían
migración, por lo que en una base creada con Alembic las tablas no existían y los
endpoints de encuestas y de sincronización offline respondían 500
("relation does not exist"). Esta migración crea:

- `surveys`: definición de la Encuesta de Satisfacción por ruta (Req 20.1, 20.3).
- `survey_responses`: respuesta única por (profile_id, path_id) e idempotente por
  `client_event_id`, sin PII (Req 20.5, 20.6, 20.8).
- `sync_actions`: acciones offline idempotentes por `client_event_id` (Req 18.2).
- `sync_path_progress`: progreso por (profile_id, path_id) como unión de pasos
  completados (Req 18.4).

Ninguna tabla contiene PII: solo identificadores seudonimizados y contenido
validado en servidor.

Revision ID: 0011_survey_sync_tablas
Revises: 0010_chat_guardrail_decision
Create Date: 2026-11-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# identificadores de revisión usados por Alembic.
revision: str = "0011_survey_sync_tablas"
down_revision: Union[str, None] = "0010_chat_guardrail_decision"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- surveys ---
    op.create_table(
        "surveys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("path_id", sa.Uuid(), nullable=False),
        sa.Column(
            "questions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_surveys_path_id"), "surveys", ["path_id"], unique=False)

    # --- survey_responses ---
    op.create_table(
        "survey_responses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("path_id", sa.Uuid(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column(
            "answers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("geo_zone", sa.String(length=100), nullable=False),
        sa.Column("client_event_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id", "path_id", name="uq_survey_response_profile_path"
        ),
    )
    op.create_index(
        op.f("ix_survey_responses_profile_id"),
        "survey_responses",
        ["profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_survey_responses_path_id"),
        "survey_responses",
        ["path_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_survey_responses_geo_zone"),
        "survey_responses",
        ["geo_zone"],
        unique=False,
    )
    op.create_index(
        op.f("ix_survey_responses_client_event_id"),
        "survey_responses",
        ["client_event_id"],
        unique=True,
    )

    # --- sync_actions ---
    op.create_table(
        "sync_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_event_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_sync_actions_client_event_id"),
        "sync_actions",
        ["client_event_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_sync_actions_profile_id"), "sync_actions", ["profile_id"], unique=False
    )

    # --- sync_path_progress ---
    op.create_table(
        "sync_path_progress",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("path_id", sa.Uuid(), nullable=False),
        sa.Column(
            "completed_microcapsules",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id", "path_id", name="uq_sync_progress_profile_path"
        ),
    )
    op.create_index(
        op.f("ix_sync_path_progress_profile_id"),
        "sync_path_progress",
        ["profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sync_path_progress_path_id"),
        "sync_path_progress",
        ["path_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_sync_path_progress_path_id"), table_name="sync_path_progress")
    op.drop_index(
        op.f("ix_sync_path_progress_profile_id"), table_name="sync_path_progress"
    )
    op.drop_table("sync_path_progress")

    op.drop_index(op.f("ix_sync_actions_profile_id"), table_name="sync_actions")
    op.drop_index(op.f("ix_sync_actions_client_event_id"), table_name="sync_actions")
    op.drop_table("sync_actions")

    op.drop_index(
        op.f("ix_survey_responses_client_event_id"), table_name="survey_responses"
    )
    op.drop_index(op.f("ix_survey_responses_geo_zone"), table_name="survey_responses")
    op.drop_index(op.f("ix_survey_responses_path_id"), table_name="survey_responses")
    op.drop_index(
        op.f("ix_survey_responses_profile_id"), table_name="survey_responses"
    )
    op.drop_table("survey_responses")

    op.drop_index(op.f("ix_surveys_path_id"), table_name="surveys")
    op.drop_table("surveys")
