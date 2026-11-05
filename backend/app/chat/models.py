"""Modelos ORM del Conversational Agent Service.

`chat_messages` registra cada mensaje del Usuario y el ciclo de vida de su
inferencia asíncrona (pendiente → procesando → listo/fallido), con idempotencia
por `client_event_id`. Guarda SOLO contenido redactado (sin PII): la entrada ya
pasa por la redacción (Tarea 11.2) antes de persistirse, y la respuesta del
Agente es contenido generado, no PII del Usuario.

`ai_interactions` es el registro auditable de cada interacción con el modelo
(Req 3.9, 16.4): entrada redactada, salida, versión del modelo y decisión del
guardrail, correlacionado por `correlation_id`. NUNCA contiene PII.
Requisitos: 3.5, 3.6, 3.8, 3.9, 16.4.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.chat.constants import MSG_STATUS_PENDIENTE
from app.common.database import Base


class ChatMessage(Base):
    """Mensaje del Usuario y estado de su inferencia asíncrona (Req 3.5, 3.8).

    `redacted_input` guarda la entrada YA redactada (sin PII); el contenido
    original del Usuario nunca se persiste. `response` se rellena cuando la
    inferencia termina. El historial se conserva aunque la inferencia falle
    (Req 3.8). Idempotente por `client_event_id`.
    """

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Clave de idempotencia del envío; reintentos del cliente no duplican.
    client_event_id: Mapped[uuid.UUID] = mapped_column(unique=True, index=True)

    # Titular del mensaje, anclado al Usuario autenticado (anti-BOLA).
    profile_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Origen de la entrada: "texto" o "voz" (transcripción).
    source: Mapped[str] = mapped_column(String(8))

    # Entrada del Usuario YA redactada de PII (Tarea 11.2). Sin PII.
    redacted_input: Mapped[str] = mapped_column(Text)

    # Respuesta del Agente; vacía hasta que la inferencia termina.
    response: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Estado del ciclo de vida de la inferencia (pendiente/procesando/listo/fallido).
    status: Mapped[str] = mapped_column(
        String(16), default=MSG_STATUS_PENDIENTE, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AiInteraction(Base):
    """Registro auditable de una interacción con el modelo de IA (Req 3.9, 16.4).

    No contiene PII: `redacted_input` es la entrada ya redactada y el resto son
    metadatos de la inferencia. Se correlaciona con la petición por
    `correlation_id` para trazabilidad de extremo a extremo (Req 11.1).
    """

    __tablename__ = "ai_interactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Correlation-ID de la petición que originó la interacción (trazabilidad).
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)

    # Mensaje de chat asociado (si aplica), para enlazar interacción y respuesta.
    message_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    # Entrada enviada al modelo, ya redactada de PII (Req 3.10).
    redacted_input: Mapped[str] = mapped_column(Text)

    # Salida generada por el modelo.
    output: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Versión del modelo utilizado (Req 16.4).
    model_version: Mapped[str] = mapped_column(String(64))

    # Decisión del guardrail aplicada (Req 16.4); la completa la Tarea 11.5.
    guardrail_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Confianza del STT cuando el origen fue voz (Req 14.5); la completa la 11.4.
    stt_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
