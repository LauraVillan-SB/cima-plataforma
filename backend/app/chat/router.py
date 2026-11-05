"""Rutas HTTP del Conversational Agent Service (`/api/v1/chat`).

Expone el envío de mensajes de texto con inferencia asíncrona y la consulta de
su estado e historial. El envío valida (Tarea 11.1), redacta la PII (Tarea 11.2)
y encola la inferencia, respondiendo 202 sin bloquear la petición (Req 3.5). El
titular se resuelve desde la cookie de sesión (anti-BOLA); las respuestas no
exponen PII.
Requisitos: 3.1, 3.5, 3.6, 3.7, 3.8, 12.4.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat import service
from app.chat.dto import ChatHistory, ChatMessageEnqueueIn, ChatMessageStatusOut
from app.chat.service import InferenceQueue, NullInferenceQueue
from app.common.database import get_session
from app.common.security import get_current_user_id

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

# Cola de inferencia por defecto. En integración se sustituye por el broker real
# mediante override de esta dependencia.
_default_queue = NullInferenceQueue()


def get_inference_queue() -> InferenceQueue:
    """Dependencia que provee la cola de inferencia (inyectable en pruebas/integración)."""
    return _default_queue


@router.post(
    "/mensajes",
    response_model=ChatMessageStatusOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enviar_mensaje(
    data: ChatMessageEnqueueIn,
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    queue: InferenceQueue = Depends(get_inference_queue),
) -> ChatMessageStatusOut:
    """Valida, redacta y encola el mensaje; responde 202 con el estado inicial."""
    return await service.encolar_mensaje_texto(db, current_user_id, data, queue)


@router.get("/mensajes/{mensaje_id}", response_model=ChatMessageStatusOut)
async def estado_mensaje(
    mensaje_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> ChatMessageStatusOut:
    """Devuelve el estado del mensaje del Usuario, con indicador y timeout aplicados."""
    return await service.obtener_estado_mensaje(db, current_user_id, mensaje_id)


@router.get("/historial", response_model=ChatHistory)
async def historial(
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> ChatHistory:
    """Devuelve el historial de conversación del Usuario autenticado (sin PII)."""
    return await service.obtener_historial(db, current_user_id)
