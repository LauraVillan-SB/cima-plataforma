"""Esquemas (DTO) del Metrics Service con validación estricta en servidor.

Aplica allowlist de campos (rechaza claves inesperadas), normalización (trim) y
validación de tipo, formato y rango (Req 8.1, 8.2). Los reportes exponen solo
datos agregados por zona, nunca PII individual (Req 8.5).
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, field_validator

from app.metrics.constants import ALLOWED_EVENT_TYPES, GEO_ZONE_MAX_LENGTH


class MetricEventCreate(BaseModel):
    """Datos de entrada para registrar un evento de métrica.

    `extra="forbid"` implementa la allowlist de campos: cualquier clave no
    declarada hace fallar la validación (Zero Trust Input).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    client_event_id: uuid.UUID
    profile_id: uuid.UUID
    event_type: str
    geo_zone: str | None = None

    @field_validator("event_type")
    @classmethod
    def _validate_event_type(cls, value: str) -> str:
        """Valida que el tipo de evento pertenezca a la allowlist (Req 8.1)."""
        normalized = value.lower()
        if normalized not in ALLOWED_EVENT_TYPES:
            raise ValueError("El tipo de evento no está en la lista permitida.")
        return normalized

    @field_validator("geo_zone")
    @classmethod
    def _validate_geo_zone(cls, value: str | None) -> str | None:
        """Valida que la zona, si viene, no exceda el máximo permitido (Req 8.2)."""
        if value is None or value == "":
            return None
        if len(value) > GEO_ZONE_MAX_LENGTH:
            raise ValueError(
                f"La zona geográfica no puede exceder {GEO_ZONE_MAX_LENGTH} caracteres."
            )
        return value


class MetricEventResponse(BaseModel):
    """DTO de salida tras registrar un evento; sin PII (Req 8.5)."""

    id: uuid.UUID
    event_type: str
    geo_zone: str
    classified: bool


class ZoneAggregate(BaseModel):
    """Agregado de eventos por zona y tipo; sin campos identificables (Req 8.5)."""

    geo_zone: str
    event_type: str
    event_count: int
    distinct_users: int


class MetricsReport(BaseModel):
    """Reporte agregado con supresión por k-anonimato aplicada (Req 8.6)."""

    aggregates: list[ZoneAggregate]
