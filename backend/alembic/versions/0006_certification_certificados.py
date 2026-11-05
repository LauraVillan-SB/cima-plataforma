"""Certification Service: certificates

Crea la tabla del Certification Service (Tarea 15):
- `certificates`: Certificado emitido por (profile_id, path_id), único por ese par
  para garantizar la idempotencia de la emisión (Req 6.4), con código de
  verificación único alfanumérico de 16–64 caracteres (Req 6.3).

La tabla no contiene PII: solo identificadores internos, la fecha de emisión y el
código de verificación.

Revision ID: 0006_certification_certificados
Revises: 0005_assessment_evaluaciones
Create Date: 2026-10-31
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# identificadores de revisión usados por Alembic.
revision: str = "0006_certification_certificados"
down_revision: Union[str, None] = "0005_assessment_evaluaciones"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "certificates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("path_id", sa.Uuid(), nullable=False),
        sa.Column("verification_code", sa.String(length=64), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id", "path_id", name="uq_certificate_profile_path"
        ),
    )
    op.create_index(
        op.f("ix_certificates_verification_code"),
        "certificates",
        ["verification_code"],
        unique=True,
    )
    op.create_index(
        op.f("ix_certificates_profile_id"), "certificates", ["profile_id"], unique=False
    )
    op.create_index(
        op.f("ix_certificates_path_id"), "certificates", ["path_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_certificates_path_id"), table_name="certificates")
    op.drop_index(op.f("ix_certificates_profile_id"), table_name="certificates")
    op.drop_index(
        op.f("ix_certificates_verification_code"), table_name="certificates"
    )
    op.drop_table("certificates")
