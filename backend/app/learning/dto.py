"""Esquemas (DTO) del Learning Service con validación estricta en servidor.

Aplica allowlist de campos (rechaza claves inesperadas), normalización (trim) y
validación de tipo, formato y rango (Req 4.1, 4.2, 7.6). Las respuestas exponen
solo los campos autorizados; este dominio no maneja PII del Usuario, pero igual
se usan DTOs de salida con allowlist (nunca el objeto ORM completo, Req 9.5).
"""

from __future__ import annotations

import uuid
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.learning.constants import (
    ALLOWED_TOPICS,
    MAX_DURATION_SEC,
    MAX_ELAPSED_SEC,
    MIN_DURATION_SEC,
    PACE_STANDARD,
    YOUTUBE_VIDEO_ID_PATTERN,
)


class VideoOut(BaseModel):
    """Video de apoyo de YouTube de una microcápsula.

    Solo expone el identificador validado, el crédito (título y canal) y la dirección de
    incrustación construida por el backend; el cliente no arma URLs. El video es un
    complemento: el contenido de texto es lo principal y funciona sin conexión.
    """

    model_config = ConfigDict(extra="forbid")

    video_id: str = Field(pattern=YOUTUBE_VIDEO_ID_PATTERN)
    title: str
    channel: str
    embed_url: str


class MicrocapsuleResponse(BaseModel):
    """DTO de salida de una microcápsula entregada al Usuario.

    Garantiza, a nivel de contrato, que el tema pertenece a la allowlist
    (Property 11) y que la duración está en el rango permitido (Property 10). El
    contenido (`title`, `summary`, `paragraphs`, `key_points`) es texto plano y es
    opcional para no romper cápsulas anteriores; `video` es un complemento opcional.
    """

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    topic: str
    activity_tags: list[str]
    duration_sec: int
    difficulty: int
    title: Optional[str] = None
    summary: Optional[str] = None
    paragraphs: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    video: Optional[VideoOut] = None

    @field_validator("topic")
    @classmethod
    def _validate_topic(cls, value: str) -> str:
        """Valida que el tema sea exactamente uno de la allowlist (Req 4.2)."""
        if value not in ALLOWED_TOPICS:
            raise ValueError("El tema de la microcápsula no está en la lista permitida.")
        return value

    @field_validator("duration_sec")
    @classmethod
    def _validate_duration(cls, value: int) -> int:
        """Valida que la duración esté entre 180 y 300 s, inclusive (Req 4.1)."""
        if not (MIN_DURATION_SEC <= value <= MAX_DURATION_SEC):
            raise ValueError(
                f"La duración debe estar entre {MIN_DURATION_SEC} y {MAX_DURATION_SEC} segundos."
            )
        return value


class MicrocapsuleSelection(BaseModel):
    """Resultado de la selección personalizada de microcápsulas.

    `fallback` indica que no hubo coincidencias para la actividad del Perfil y se
    entregó el tema general (Req 4.4). `notice` transporta la notificación al
    Usuario sobre la ausencia de contenido específico (Req 4.5), en español
    coloquial. `prompt_activity` señala que el Perfil está incompleto y el agente
    debe solicitar el tipo de cultivo/comercio (Req 4.8).
    """

    model_config = ConfigDict(extra="forbid")

    items: list[MicrocapsuleResponse]
    fallback: bool = False
    prompt_activity: bool = False
    notice: Optional[str] = None


class FinalizeRequest(BaseModel):
    """Datos de entrada para registrar la finalización de una microcápsula.

    `extra="forbid"` implementa la allowlist de campos (Zero Trust Input).
    `client_event_id` da idempotencia al registro (Req 4.7), igual que en el
    Metrics Service. `path_id` ubica la microcápsula dentro de una ruta para
    evaluar la completitud (Req 4.10).
    """

    model_config = ConfigDict(extra="forbid")

    client_event_id: uuid.UUID
    path_id: uuid.UUID
    # Tiempo que tomó completar la cápsula, medido por el cliente sin pedirle datos
    # al Usuario (Req 17.2). Opcional: sin él no hay señal de tiempo. Es solo una
    # medición; la decisión de adaptar se toma en el backend (Req 17.3).
    elapsed_seconds: Optional[int] = Field(default=None, ge=0, le=MAX_ELAPSED_SEC)


class FinalizeResponse(BaseModel):
    """DTO de salida tras registrar una finalización."""

    model_config = ConfigDict(extra="forbid")

    path_id: uuid.UUID
    microcapsule_id: uuid.UUID
    path_completed: bool
    completed_count: int
    total_count: int


class PathStatusResponse(BaseModel):
    """Estado de una ruta y el siguiente paso adaptado (Req 4.10, 17.1, 17.5)."""

    model_config = ConfigDict(extra="forbid")

    path_id: uuid.UUID
    completed: bool
    completed_count: int
    total_count: int
    next_microcapsule_id: Optional[uuid.UUID] = None
    # `adapted` es verdadero solo cuando el backend aplicó una adaptación por las
    # señales de progreso (Req 17.1); sin señales suficientes es falso y la ruta es
    # la estándar (Req 17.5). `simplify` y `pace` son lo que el cliente debe aplicar
    # a la microcápsula siguiente; el cliente no decide ni calcula nada (Req 17.3).
    adapted: bool = False
    simplify: bool = False
    pace: Literal["standard", "slow"] = PACE_STANDARD


class RouteCapsuleOut(BaseModel):
    """Una microcápsula dentro de una ruta, con su estado para el Usuario autenticado.

    `status` es `completed` si ya la finalizó, `next` si es la primera que le falta y
    `pending` si todavía no le toca. El orden no se impone: puede abrir cualquiera.
    """

    model_config = ConfigDict(extra="forbid")

    position: int
    status: Literal["completed", "next", "pending"]
    capsule: MicrocapsuleResponse


class RouteOut(BaseModel):
    """Ruta de aprendizaje con el avance del Usuario autenticado y sus cápsulas."""

    model_config = ConfigDict(extra="forbid")

    path_id: uuid.UUID
    title: Optional[str] = None
    summary: Optional[str] = None
    audience_tags: list[str]
    total_count: int
    completed_count: int
    completed: bool
    next_microcapsule_id: Optional[uuid.UUID] = None
    assessment_passed: bool
    items: list[RouteCapsuleOut]


class RoutesResponse(BaseModel):
    """Rutas relevantes para el Usuario autenticado, la suya primero y la general después."""

    model_config = ConfigDict(extra="forbid")

    routes: list[RouteOut]
