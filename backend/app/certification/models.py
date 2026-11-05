"""Modelo ORM del Certification Service.

`certificates` almacena un Certificado digital emitido a un Usuario por completar
y aprobar una Ruta_de_Aprendizaje. La restricción UNIQUE(`profile_id`,`path_id`)
garantiza la idempotencia de la emisión: un solo Certificado por titular y ruta
(Req 6.4). El `verification_code` es un código verificable alfanumérico de 16–64
caracteres (Req 6.3).

La tabla no contiene PII: solo identificadores internos, la fecha de emisión y el
código de verificación.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base


class Certificate(Base):
    """Certificado digital asociado a un Perfil y una Ruta_de_Aprendizaje."""

    __tablename__ = "certificates"
    __table_args__ = (
        UniqueConstraint("profile_id", "path_id", name="uq_certificate_profile_path"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Titular del Certificado; la autorización de consulta se verifica contra él
    # (anti-BOLA, Req 6.5–6.7).
    profile_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Ruta de aprendizaje certificada.
    path_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Código único verificable, alfanumérico de 16–64 caracteres (Req 6.3).
    verification_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # Fecha de emisión (ISO-8601 con zona horaria, Req 6.3).
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
