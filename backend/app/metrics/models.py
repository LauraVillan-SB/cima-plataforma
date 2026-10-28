"""Modelos ORM del Metrics Service.

`metric_events` almacena cada evento de métrica de forma idempotente por
`client_event_id` (UUID v4). El `profile_id` se guarda seudonimizado y los
reportes se construyen de forma agregada, nunca exponiendo PII individual.
Requisitos: 8.1, 8.2, 8.4.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base


class MetricEvent(Base):
    """Evento de métrica registrado por zona geográfica.

    La unicidad de `client_event_id` garantiza la idempotencia del registro:
    reintentos con el mismo id no duplican el evento (Req 8.4).
    """

    __tablename__ = "metric_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Identificador de idempotencia generado por el cliente (UUID v4). Único.
    client_event_id: Mapped[uuid.UUID] = mapped_column(unique=True, index=True)

    # Perfil seudonimizado asociado al evento (no es PII directa).
    profile_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Zona geográfica del evento; "sin_zona" cuando no se pudo clasificar.
    geo_zone: Mapped[str] = mapped_column(String(100), index=True)

    # Tipo de evento (valor de la allowlist de dominio).
    event_type: Mapped[str] = mapped_column(String(32), index=True)

    # Indica si el evento quedó clasificado en una zona conocida (Req 8.2).
    classified: Mapped[bool] = mapped_column(Boolean, default=True)

    # Marca temporal del registro (ISO-8601, con zona horaria).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
