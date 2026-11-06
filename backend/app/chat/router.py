"""Rutas HTTP del Conversational Agent Service (`/api/v1/chat`).

Expone el envío de mensajes de texto (encola la inferencia y responde 202), la
consulta del resultado por id y el historial del Usuario. El titular se resuelve
desde la cookie de sesión (anti-BOLA). La inferencia se ejecuta en segundo plano
con `BackgroundTasks`; en producción el encolado puede moverse a una cola/worker
dedicados sin cambiar este contrato (Req 3.5, 12.4).
Requisitos: 3.1, 3.5, 3.6, 3.7, 3.8.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat import service
from app.chat.constants import ESTADO_REPETIR_VOZ, VOICE_MAX_BYTES
from app.chat.dto import (
    ChatHistory,
    ChatMessageAccepted,
    ChatMessageResult,
    ChatTextMessageIn,
)
from app.chat.errors import NotaDeVozInvalidaError
from app.common.database import async_session_factory, get_session
from app.common.security import get_current_user_id

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


async def _procesar_en_background(interaction_id: uuid.UUID) -> None:
    """Procesa la inferencia con una sesión propia fuera del ciclo del request.

    La sesión del request se cierra al responder el 202, así que el worker abre
    su propia sesión para no usar una ya cerrada. Usa los modelos de respaldo por
    defecto (LLM/TTS); el proveedor real se inyecta cuando esté disponible.
    """
    async with async_session_factory() as db:
        await service.procesar_inferencia(db, interaction_id)


@router.post(
    "/mensajes",
    response_model=ChatMessageAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enviar_mensaje(
    data: ChatTextMessageIn,
    tareas: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> ChatMessageAccepted:
    """Encola un mensaje de texto para inferencia y responde 202 (Req 3.5)."""
    acuse = await service.encolar_mensaje_texto(db, current_user_id, data)
    tareas.add_task(_procesar_en_background, acuse.id)
    return acuse


@router.post(
    "/mensajes/voz",
    response_model=ChatMessageAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enviar_nota_de_voz(
    tareas: BackgroundTasks,
    audio: UploadFile = File(...),
    duracion_segundos: float = Form(...),
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> ChatMessageAccepted:
    """Recibe una Nota de Voz, la transcribe y encola la inferencia (Req 14.2, 14.5).

    La duración la mide el cliente y el servidor la valida contra el rango
    permitido (1–120 s). El audio se lee acotado al tamaño máximo y no se
    persiste: solo se usa para transcribir (Req 14.6). Si el STT no es confiable,
    el acuse vuelve con estado "repetir_voz".
    """
    contenido = await audio.read(VOICE_MAX_BYTES + 1)
    if len(contenido) > VOICE_MAX_BYTES:
        raise NotaDeVozInvalidaError(internal_detail="voice upload exceeds max size")
    acuse = await service.encolar_nota_de_voz(
        db, current_user_id, contenido, duracion_segundos
    )
    if acuse.status != ESTADO_REPETIR_VOZ:
        tareas.add_task(_procesar_en_background, acuse.id)
    return acuse


@router.get("/mensajes/{mensaje_id}", response_model=ChatMessageResult)
async def consultar_mensaje(
    mensaje_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> ChatMessageResult:
    """Consulta el estado o el resultado de una inferencia del Usuario (Req 3.7, 3.8)."""
    return await service.obtener_resultado(db, current_user_id, mensaje_id)


@router.get("/historial", response_model=ChatHistory)
async def consultar_historial(
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> ChatHistory:
    """Devuelve el historial de conversación del Usuario autenticado (Req 3.8)."""
    return await service.obtener_historial(db, current_user_id)
