"""Modelos ORM del Gamification Service.

`user_badges` guarda cada Insignia otorgada a un Perfil. La restricción
UNIQUE(profile_id, badge_code) impide duplicados (Req 19.5) y `client_event_id`
único hace idempotentes los reintentos del evento origen (Req 19.6).
`user_points` guarda el total de puntos por Perfil (una fila por Perfil).
Ninguna tabla contiene PII: solo identificadores internos y códigos.
Requisitos: 19.2, 19.5, 19.6.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base


class UserBadge(Base):
    """Insignia otorgada a un Perfil; única por (perfil, insignia) (Req 19.5)."""

    __tablename__ = "user_badges"
    __table_args__ = (
        UniqueConstraint("profile_id", "badge_code", name="uq_user_badge_profile_badge"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Titular de la Insignia (identificador interno, no PII).
    profile_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Código de la Insignia del catálogo de reglas del backend.
    badge_code: Mapped[str] = mapped_column(String(64))

    # Clave de idempotencia del evento origen; los reintentos la reutilizan.
    client_event_id: Mapped[uuid.UUID] = mapped_column(unique=True, index=True)

    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UserPoints(Base):
    """Total de puntos acumulados por un Perfil (Req 19.2)."""

    __tablename__ = "user_points"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Una sola fila por Perfil.
    profile_id: Mapped[uuid.UUID] = mapped_column(unique=True, index=True)

    total_points: Mapped[int] = mapped_column(Integer, default=0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
