"""Modelos ORM del Assessment Service.

Define las entidades de evaluación:
- `assessments`: evaluación asociada a una Ruta_de_Aprendizaje, con las preguntas
  y su clave de respuestas en JSONB para validar y calificar en el servidor
  (Req 7.1, 7.6). El umbral de aprobación se acota a 0–100 (Req 7.3).
- `assessment_attempts`: intentos de un Usuario sobre una ruta, con el puntaje
  (0–100), el resultado, el número de intento (≤ 3) y la ventana de enfriamiento
  de 24 h tras agotarlos (Req 7.2, 7.4, 7.5).

Ninguna tabla contiene PII: solo identificadores internos, metadatos de la
evaluación y resultados numéricos.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base


class Assessment(Base):
    """Evaluación de una ruta: preguntas y umbral de aprobación.

    `questions` guarda la definición completa (enunciado, opciones y la opción
    correcta) usada en el servidor para validar y calificar; la clave correcta
    nunca se expone al cliente (Req 7.6).
    """

    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Ruta de aprendizaje a la que pertenece la evaluación (Req 7.1).
    path_id: Mapped[uuid.UUID] = mapped_column(unique=True, index=True)

    # Definición de preguntas (enunciado, opciones y opción correcta) validada
    # en servidor. Estructura: [{"id", "prompt", "options": [...], "correct": int}].
    questions: Mapped[list[dict]] = mapped_column(JSONB, default=list)

    # Umbral de aprobación 0–100 (default 70, Req 7.3).
    pass_threshold: Mapped[int] = mapped_column(Integer, default=70)


class AssessmentAttempt(Base):
    """Intento de un Usuario sobre la evaluación de una ruta.

    Registra el puntaje (0–100), si aprobó, el número de intento (≤ 3) y la
    ventana de enfriamiento tras agotar los intentos (Req 7.2, 7.4, 7.5). Se
    ancla a `profile_id` para la autorización por propiedad (anti-BOLA).
    """

    __tablename__ = "assessment_attempts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Titular del intento; se ancla a la identidad autenticada (anti-BOLA).
    profile_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Ruta de aprendizaje evaluada.
    path_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Puntaje obtenido en escala 0–100 (Req 7.2).
    score: Mapped[int] = mapped_column(Integer)

    # Resultado: aprobado si el puntaje alcanzó el umbral (Req 7.3).
    passed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Número de intento consumido (1..3) dentro del ciclo vigente (Req 7.4).
    attempt_number: Mapped[int] = mapped_column(Integer)

    # Fin de la ventana de enfriamiento tras agotar los intentos (Req 7.5);
    # None mientras no se haya activado el enfriamiento.
    cooldown_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
