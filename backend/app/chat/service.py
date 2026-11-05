"""Lógica de negocio del Conversational Agent Service — inferencia asíncrona.

Implementa el encolado de mensajes para inferencia y la consulta de su estado
(Tarea 11.3, Req 3.1, 3.5, 3.6, 3.7, 3.8). El flujo de envío es:

1. Validar el texto (Tarea 11.1) — rechaza vacío/>2000 sin tocar el modelo.
2. Redactar la PII (Tarea 11.2) — si falla, no se encola nada (Req 3.11).
3. Persistir el mensaje `pendiente` (idempotente por `client_event_id`) y
   registrar la interacción auditable sin PII (Req 3.9).
4. Encolar la inferencia en la cola inyectada y responder de inmediato (202):
   la petición del Usuario no se bloquea esperando al modelo.

La cola/worker concreta (broker de mensajes + proceso de inferencia) se inyecta
a través de `InferenceQueue`; aquí se define la interfaz y una implementación
nula para desarrollo/pruebas. El worker real toma el mensaje, invoca el modelo
y actualiza el estado a `listo`/`fallido`.

El titular se resuelve desde la cookie de sesión (anti-BOLA); el cliente nunca
envía `profile_id`. Se usa el ORM parametrizado y no se registra PII.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.constants import (
    INFERENCE_TIMEOUT_SECONDS,
    MSG_SOURCE_TEXTO,
    MSG_STATUS_FALLIDO,
    MSG_STATUS_LISTO,
    MSG_STATUS_PENDIENTE,
    PROCESSING_INDICATOR_SECONDS,
)
from app.chat.dto import (
    ChatHistory,
    ChatHistoryItem,
    ChatMessageEnqueueIn,
    ChatMessageStatusOut,
)
from app.chat.models import AiInteraction, ChatMessage
from app.chat.redaction import redactar_pii
from app.chat.validation import validar_mensaje_texto
from app.common.correlation import get_correlation_id
from app.common.errors import NotFoundError
from app.common.logging import log_event

logger = logging.getLogger("cima.chat")

# Versión del modelo registrada en la auditoría mientras no hay integración real.
_MODEL_VERSION_PLACEHOLDER = "pendiente-integracion"


class InferenceQueue(Protocol):
    """Interfaz de la cola de inferencia asíncrona (Req 12.4).

    El servicio solo encola; el worker que consume la cola invoca el modelo y
    actualiza el estado del mensaje. Se inyecta para desacoplar el broker real
    (p. ej. SQS/RabbitMQ) y poder probar sin infraestructura.
    """

    async def enqueue(self, message_id: uuid.UUID, correlation_id: str) -> None:
        """Encola la inferencia del mensaje indicado."""
        ...


class NullInferenceQueue:
    """Cola nula para desarrollo/pruebas: registra el encolado sin procesar.

    No invoca ningún modelo; deja el mensaje en `pendiente`. El worker real
    reemplaza esta implementación en integración.
    """

    async def enqueue(self, message_id: uuid.UUID, correlation_id: str) -> None:
        log_event(
            logger,
            "chat_inference_enqueued",
            message_id=str(message_id),
        )


async def encolar_mensaje_texto(
    db: AsyncSession,
    current_user_id: uuid.UUID,
    data: ChatMessageEnqueueIn,
    queue: InferenceQueue,
) -> ChatMessageStatusOut:
    """Valida, redacta y encola un mensaje de texto para inferencia (Req 3.1, 3.5).

    Idempotente por `client_event_id`: un reenvío devuelve el mensaje existente
    sin volver a encolar. La validación de longitud (Tarea 11.1) y la redacción
    de PII (Tarea 11.2) ocurren antes de persistir y encolar; si la redacción
    falla, se propaga `RedaccionPiiError` y no se encola nada (Req 3.11).

    Returns:
        El estado inicial del mensaje (`pendiente`) para responder con 202.
    """
    existing = await db.scalar(
        select(ChatMessage).where(ChatMessage.client_event_id == data.client_event_id)
    )
    if existing is not None:
        log_event(logger, "chat_message_idempotent_hit", message_id=str(existing.id))
        return _to_status(existing)

    # 11.1: validación de longitud (lanza error de dominio si no cumple).
    texto = validar_mensaje_texto(data.text)
    # 11.2: redacción de PII antes de persistir/encolar (lanza si no puede).
    redactado = redactar_pii(texto)

    mensaje = ChatMessage(
        client_event_id=data.client_event_id,
        profile_id=current_user_id,
        source=MSG_SOURCE_TEXTO,
        redacted_input=redactado.texto,
        status=MSG_STATUS_PENDIENTE,
    )
    db.add(mensaje)
    await db.commit()
    await db.refresh(mensaje)

    correlation_id = get_correlation_id()
    # Registro auditable de la interacción, sin PII (Req 3.9, 16.4).
    db.add(
        AiInteraction(
            correlation_id=correlation_id,
            message_id=mensaje.id,
            redacted_input=redactado.texto,
            model_version=_MODEL_VERSION_PLACEHOLDER,
        )
    )
    await db.commit()

    await queue.enqueue(mensaje.id, correlation_id)
    log_event(
        logger,
        "chat_message_accepted",
        message_id=str(mensaje.id),
        categorias=sorted(redactado.categorias.keys()),
    )
    return _to_status(mensaje)


async def obtener_estado_mensaje(
    db: AsyncSession, current_user_id: uuid.UUID, message_id: uuid.UUID
) -> ChatMessageStatusOut:
    """Devuelve el estado de un mensaje del Usuario, aplicando el timeout (Req 3.7, 3.8).

    Si el mensaje sigue sin respuesta pasados `INFERENCE_TIMEOUT_SECONDS` desde su
    creación, se marca `fallido` (servicio no disponible) conservando el mensaje
    en el historial (Req 3.8). Solo el titular puede consultar su mensaje
    (anti-BOLA): un mensaje de otro Usuario se trata como inexistente.
    """
    mensaje = await db.get(ChatMessage, message_id)
    if mensaje is None or mensaje.profile_id != current_user_id:
        # No se revela la existencia de mensajes de otros Usuarios (Req 9.6).
        raise NotFoundError(internal_detail="chat message not found for current user")

    if _debe_marcar_timeout(mensaje):
        mensaje.status = MSG_STATUS_FALLIDO
        await db.commit()
        await db.refresh(mensaje)
        log_event(logger, "chat_message_timed_out", message_id=str(mensaje.id))

    return _to_status(mensaje)


async def obtener_historial(
    db: AsyncSession, current_user_id: uuid.UUID
) -> ChatHistory:
    """Devuelve el historial de conversación del Usuario autenticado (Req 3.8).

    Anclado al titular (anti-BOLA); ordenado del más reciente al más antiguo. No
    expone PII: `redacted_input` ya viene redactado.
    """
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.profile_id == current_user_id)
        .order_by(ChatMessage.created_at.desc())
    )
    result = await db.scalars(stmt)
    items = [
        ChatHistoryItem(
            id=m.id,
            status=m.status,
            source=m.source,
            redacted_input=m.redacted_input,
            response=m.response,
        )
        for m in result.all()
    ]
    return ChatHistory(items=items)


def _debe_marcar_timeout(mensaje: ChatMessage) -> bool:
    """Indica si un mensaje aún sin respuesta superó el tope de 60 s (Req 3.8)."""
    if mensaje.status in (MSG_STATUS_LISTO, MSG_STATUS_FALLIDO):
        return False
    if mensaje.created_at is None:
        return False
    transcurrido = (datetime.now(timezone.utc) - mensaje.created_at).total_seconds()
    return transcurrido >= INFERENCE_TIMEOUT_SECONDS


def _show_indicator(mensaje: ChatMessage) -> bool:
    """Indica si el cliente debe mostrar el indicador de procesamiento (Req 3.7).

    Se muestra mientras el mensaje no tiene respuesta ni ha fallado y ya pasó el
    umbral de `PROCESSING_INDICATOR_SECONDS` desde su creación.
    """
    if mensaje.status in (MSG_STATUS_LISTO, MSG_STATUS_FALLIDO):
        return False
    if mensaje.created_at is None:
        return True
    transcurrido = (datetime.now(timezone.utc) - mensaje.created_at).total_seconds()
    return transcurrido >= PROCESSING_INDICATOR_SECONDS


def _to_status(mensaje: ChatMessage) -> ChatMessageStatusOut:
    """Construye el DTO de estado de un mensaje (sin PII, Req 3.9)."""
    return ChatMessageStatusOut(
        id=mensaje.id,
        status=mensaje.status,
        source=mensaje.source,
        redacted_input=mensaje.redacted_input,
        response=mensaje.response,
        show_indicator=_show_indicator(mensaje),
    )
