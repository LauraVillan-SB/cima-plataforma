"""Modelos ORM del Survey Service.

`surveys` define la Encuesta de Satisfacción asociada a una ruta (preguntas con
escala 1–5). `survey_responses` almacena cada respuesta de forma idempotente por
`client_event_id` y con restricción UNIQUE(profile_id, path_id) para evitar
respuestas duplicadas por ruta y Usuario. El contenido registrado excluye PII.
Requisitos: 20.1, 20.3, 20.5, 20.6, 20.8.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base


class Survey(Base):
    """Definición de una Encuesta de Satisfacción para una ruta (Req 20.1)."""

    __tablename__ = "surveys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Ruta de aprendizaje o hito que dispara la encuesta.
    path_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Definición de preguntas con tipos/escala para validación en servidor;
    # incluye al menos una calificación en escala 1–5 (Req 20.1, 20.3).
    questions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Indica si la encuesta está vigente para presentación.
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SurveyResponse(Base):
    """Respuesta a la Encuesta de Satisfacción, agregada y sin PII (Req 20.5)."""

    __tablename__ = "survey_responses"
    __table_args__ = (
        # Idempotencia de presentación/registro: una respuesta por ruta y Usuario.
        UniqueConstraint("profile_id", "path_id", name="uq_survey_response_profile_path"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Titular seudonimizado, verificado contra el Usuario autenticado (Req 20.5).
    profile_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Ruta de aprendizaje asociada a la encuesta.
    path_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Calificación dentro de la escala permitida 1–5 (Req 20.3).
    rating: Mapped[int] = mapped_column(Integer)

    # Estructura validada en servidor; sin PII en el contenido registrado (Req 20.4).
    answers: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Zona geográfica para agregación; "sin_zona" si ausente (Req 20.7).
    geo_zone: Mapped[str] = mapped_column(String(100), index=True)

    # Clave de idempotencia del registro; reintentos reutilizan el valor (Req 20.6).
    client_event_id: Mapped[uuid.UUID] = mapped_column(unique=True, index=True)

    # Base para la política de retención/anonimización a 90 días (Req 20.8).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
