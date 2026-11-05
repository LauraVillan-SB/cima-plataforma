"""Esquemas (DTO) del Assessment Service con validación estricta en servidor.

Aplica allowlist de campos (`extra="forbid"`) y validación de tipo, formato y
rango antes de calcular cualquier puntaje (Req 7.6, 7.7, Property 25). La
presentación de la evaluación nunca incluye la opción correcta de cada pregunta
(la clave vive solo en el servidor, Req 7.6).
"""

from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class QuestionOut(BaseModel):
    """Pregunta tal como se presenta al Usuario, sin la respuesta correcta."""

    model_config = ConfigDict(extra="forbid")

    id: int
    prompt: str
    options: list[str]


class AssessmentOut(BaseModel):
    """Presentación de la evaluación de una ruta (Req 7.1).

    No expone la clave de respuestas: solo enunciados y opciones.
    """

    model_config = ConfigDict(extra="forbid")

    path_id: uuid.UUID
    questions: list[QuestionOut]


class AnswerItem(BaseModel):
    """Respuesta a una pregunta: el índice de la opción elegida.

    El índice se valida como entero no negativo; la correspondencia con el número
    real de opciones se verifica en el servidor contra la definición (Req 7.6).
    """

    model_config = ConfigDict(extra="forbid")

    question_id: int = Field(ge=0)
    selected_option: int = Field(ge=0)


class AnswerSubmission(BaseModel):
    """Envío de respuestas de una evaluación.

    `extra="forbid"` implementa la allowlist de campos (Zero Trust Input). La
    validación semántica (preguntas conocidas, índices en rango, sin faltantes
    ni duplicados) se hace en el servicio antes de calcular (Req 7.6, 7.7).
    """

    model_config = ConfigDict(extra="forbid")

    answers: list[AnswerItem] = Field(min_length=1)


class AttemptResult(BaseModel):
    """Resultado de un intento de evaluación (Req 7.2–7.5)."""

    model_config = ConfigDict(extra="forbid")

    path_id: uuid.UUID
    score: int
    passed: bool
    attempt_number: int
    attempts_remaining: int
    cooldown_until: Optional[str] = None
