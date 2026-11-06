"""Modelos ORM del Conversational Agent Service.

`ai_interactions` almacena cada mensaje del Usuario y su resultado de inferencia
asíncrona. El contenido se guarda YA REDACTADO (sin PII, Req 3.9, 16.4): la
redacción de PII (Tarea 11.2) se aplica antes de persistir y antes de invocar el
modelo. El registro se ancla al `profile_id` del Usuario autenticado (anti-BOLA)
y correlaciona el evento con `correlation_id`.
Requisitos: 3.5, 3.6, 3.7, 3.8, 3.9.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.chat.constants import ESTADO_ENCOLADO
from app.common.database import Base


class AiInteraction(Base):
    """Interacción con el Agente Conversacional, con su estado de inferencia."""

    __tablename__ = "ai_interactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Titular, verificado contra el Usuario autenticado (anti-BOLA).
    profile_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Entrada del Usuario YA REDACTADA (sin PII). Para texto, el mensaje
    # normalizado y redactado; para voz, la transcripción redactada (Tarea 11.4).
    input_redacted: Mapped[str] = mapped_column(Text)

    # Canal de entrada: "texto" o "voz".
    input_channel: Mapped[str] = mapped_column(String(8))

    # Estado de la inferencia: encolado | procesando | listo | error.
    status: Mapped[str] = mapped_column(String(16), default=ESTADO_ENCOLADO, index=True)

    # Respuesta del modelo cuando el estado es "listo"; nula mientras tanto.
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Referencia al audio TTS de la respuesta (no el binario); nula si no hay
    # audio o si el canal fue solo texto (Req 14.3).
    response_audio_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Versión del modelo que generó la respuesta (Req 16.4); nula hasta responder.
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Correlation-ID del evento, para trazabilidad sin PII (Req 3.9).
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
