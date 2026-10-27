"""Modelo ORM del Perfil de Usuario.

El Perfil almacena únicamente los datos mínimos (Req 9.1): teléfono, tipo de
cultivo o comercio y zona geográfica. El teléfono es PII y debe cifrarse
at-rest a nivel de infraestructura de base de datos.
Requisitos: 9.1, 1.5 (relación con la Clave gestionada por Auth).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base


class Profile(Base):
    """Perfil de Usuario con datos mínimos y marca de creación para retención."""

    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # PII: teléfono en formato normalizado. Único por usuario. Cifrado at-rest en BD.
    phone_e164: Mapped[str] = mapped_column(String(16), unique=True, index=True)

    # Tipo de cultivo o comercio (valor de la allowlist de dominio).
    activity_type: Mapped[str] = mapped_column(String(32))

    # Zona geográfica (texto libre acotado a 100 caracteres).
    geo_zone: Mapped[str] = mapped_column(String(100))

    # Marca de creación para aplicar la política de retención de 90 días (Req 9.8).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
