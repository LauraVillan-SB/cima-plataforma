"""Esquemas (DTO) del Offline Sync Service con validación estricta en servidor.

Aplica allowlist de campos (rechaza claves inesperadas) y valida el tipo de
acción y el tamaño del lote antes de aplicar (Req 18.2). El payload se valida
por tipo de acción; el contenido registrado no incluye PII.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.sync.constants import ALLOWED_ACTION_TYPES, MAX_BATCH_SIZE


class SyncAction(BaseModel):
    """Una acción offline de la cola local, con clave de idempotencia (Req 18.2)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    client_event_id: uuid.UUID
    action_type: str
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("action_type")
    @classmethod
    def _validate_action_type(cls, value: str) -> str:
        """Valida que el tipo de acción pertenezca a la allowlist (Req 18.2)."""
        normalized = value.lower()
        if normalized not in ALLOWED_ACTION_TYPES:
            raise ValueError("El tipo de acción no está en la lista permitida.")
        return normalized


class SyncBatchRequest(BaseModel):
    """Lote de acciones offline a sincronizar; tamaño acotado (Req 18.2)."""

    model_config = ConfigDict(extra="forbid")

    profile_id: uuid.UUID
    actions: list[SyncAction] = Field(min_length=1, max_length=MAX_BATCH_SIZE)


class SyncActionResult(BaseModel):
    """Resultado por acción: indica si se aplicó o si ya existía (idempotencia)."""

    client_event_id: uuid.UUID
    action_type: str
    applied: bool  # True si se aplicó ahora; False si ya estaba registrada.


class SyncBatchResponse(BaseModel):
    """Respuesta del lote: resultados por acción y conteo de nuevas aplicadas."""

    results: list[SyncActionResult]
    applied_count: int
    duplicate_count: int
