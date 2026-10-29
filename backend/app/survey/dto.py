"""Esquemas (DTO) del Survey Service con validación estricta en servidor.

Aplica allowlist de campos (rechaza claves inesperadas), normalización (trim) y
validación de tipo, formato y rango (calificación 1–5) antes de registrar
(Req 20.3, 20.4). Los reportes exponen solo datos agregados por zona, nunca PII
individual (Req 20.7).
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.survey.constants import GEO_ZONE_MAX_LENGTH, RATING_MAX, RATING_MIN


class SurveyResponseCreate(BaseModel):
    """Datos de entrada para registrar una respuesta de encuesta.

    `extra="forbid"` implementa la allowlist de campos: cualquier clave no
    declarada hace fallar la validación (Zero Trust Input, Req 20.3).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    client_event_id: uuid.UUID
    profile_id: uuid.UUID
    rating: int = Field(ge=RATING_MIN, le=RATING_MAX)
    answers: dict[str, Any] = Field(default_factory=dict)
    geo_zone: str | None = None

    @field_validator("geo_zone")
    @classmethod
    def _validate_geo_zone(cls, value: str | None) -> str | None:
        """Valida que la zona, si viene, no exceda el máximo permitido (Req 20.5)."""
        if value is None or value == "":
            return None
        if len(value) > GEO_ZONE_MAX_LENGTH:
            raise ValueError(
                f"La zona geográfica no puede exceder {GEO_ZONE_MAX_LENGTH} caracteres."
            )
        return value


class SurveyQuestion(BaseModel):
    """Pregunta de la encuesta expuesta en la presentación (Req 20.1)."""

    id: str
    text: str
    type: str


class SurveyPresentation(BaseModel):
    """DTO de presentación de la encuesta; breve y opcional (Req 20.1, 20.2)."""

    survey_id: uuid.UUID
    path_id: uuid.UUID
    questions: list[SurveyQuestion]
    already_answered: bool


class SurveyResponseResult(BaseModel):
    """DTO de salida tras registrar una respuesta; sin PII (Req 20.4)."""

    id: uuid.UUID
    path_id: uuid.UUID
    rating: int
    geo_zone: str


class ZoneSatisfaction(BaseModel):
    """Agregado de satisfacción por zona; sin campos identificables (Req 20.7)."""

    geo_zone: str
    response_count: int
    distinct_users: int
    average_rating: float


class SatisfactionReport(BaseModel):
    """Reporte agregado con supresión por k-anonimato aplicada (Req 20.7)."""

    zones: list[ZoneSatisfaction]
