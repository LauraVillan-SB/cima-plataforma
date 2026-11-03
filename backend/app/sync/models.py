"""Modelos ORM del Offline Sync Service.

`sync_actions` registra cada acción sincronizada de forma idempotente por
`client_event_id` (UUID v4): reaplicar un lote no crea duplicados (Property 36).
`sync_path_progress` mantiene el progreso de ruta por Usuario como la UNIÓN de
los pasos completados, de modo que la fusión nunca pierde un paso ya hecho
(Property 37).
Requisitos: 18.2, 18.4.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base


class SyncAction(Base):
    """Acción offline aplicada, con idempotencia por `client_event_id` (Req 18.2)."""

    __tablename__ = "sync_actions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Clave de idempotencia generada por el cliente (UUID v4). Única: reintentos
    # con el mismo id no vuelven a aplicar la acción.
    client_event_id: Mapped[uuid.UUID] = mapped_column(unique=True, index=True)

    # Titular seudonimizado al que pertenece la acción (verificado en backend).
    profile_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Tipo de acción (valor de la allowlist de dominio).
    action_type: Mapped[str] = mapped_column(String(32))

    # Contenido de la acción validado en servidor; sin PII.
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Marca de aplicación en el servidor (ISO-8601).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SyncPathProgress(Base):
    """Progreso de ruta por Usuario como unión de pasos completados (Req 18.4)."""

    __tablename__ = "sync_path_progress"
    __table_args__ = (
        # Un único registro de progreso por ruta y Usuario.
        UniqueConstraint("profile_id", "path_id", name="uq_sync_progress_profile_path"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    profile_id: Mapped[uuid.UUID] = mapped_column(index=True)
    path_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Conjunto (sin duplicados) de microcápsulas completadas; crece monótonamente.
    completed_microcapsules: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list
    )

    # True cuando la ruta se considera completada.
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
