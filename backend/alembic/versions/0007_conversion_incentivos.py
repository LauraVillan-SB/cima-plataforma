"""Conversion Service: incentives

Crea la tabla del Conversion Service para la entrega de incentivos (Tarea 16.1):
- `incentives`: incentivo asociado a una ruta completada, único por
  (profile_id, path_id). Guarda el estado de entrega (`entregado`/`pendiente`) y
  el contador de reintentos (0–3) para la política de reintentos (Req 5.1, 5.2,
  5.3). No contiene PII: solo identificadores internos y metadatos.

Revision ID: 0007_conversion_incentivos
Revises: 0006_certification_certificados
Create Date: 2026-11-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# identificadores de revisión usados por Alembic.
revision: str = "0007_conversion_incentivos"
down_revision: Union[str, None] = "0006_certification_certificados"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "incentives",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("path_id", sa.Uuid(), nullable=False),
        sa.Column("incentive_type", sa.String(length=64), nullable=False),
        sa.Column(
            "delivery_status",
            sa.String(length=16),
            server_default="pendiente",
            nullable=False,
        ),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "path_id", name="uq_incentive_profile_path"),
    )
    op.create_index(
        op.f("ix_incentives_profile_id"), "incentives", ["profile_id"], unique=False
    )
    op.create_index(
        op.f("ix_incentives_path_id"), "incentives", ["path_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_incentives_path_id"), table_name="incentives")
    op.drop_index(op.f("ix_incentives_profile_id"), table_name="incentives")
    op.drop_table("incentives")
