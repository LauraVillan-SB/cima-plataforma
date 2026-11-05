"""Rutas HTTP del Learning Service (`/api/v1/aprendizaje`).

Expone la selección personalizada de microcápsulas, el registro de finalización
(idempotente) y el estado de la ruta con el siguiente paso adaptado. La
autorización es siempre de backend: las operaciones usan la identidad
autenticada (`current_user_id`) y el progreso se ancla a ese titular (anti-BOLA).
Requisitos: 4.1–4.10, 17.1, 17.5.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_session
from app.common.security import get_current_user_id
from app.learning import service
from app.learning.dto import (
    FinalizeRequest,
    FinalizeResponse,
    MicrocapsuleSelection,
    PathStatusResponse,
)
from app.profile.models import Profile

router = APIRouter(prefix="/api/v1/aprendizaje", tags=["aprendizaje"])


@router.get("/microcapsulas", response_model=MicrocapsuleSelection)
async def listar_microcapsulas(
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> MicrocapsuleSelection:
    """Entrega microcápsulas personalizadas según la actividad del Perfil.

    La actividad se resuelve en servidor desde el Perfil del Usuario autenticado;
    nunca se acepta del cliente. Si el Perfil no tiene actividad, la respuesta
    marca `prompt_activity` para que el agente la solicite (Req 4.8, 4.9).
    """
    profile = await db.get(Profile, current_user_id)
    activity_type = profile.activity_type if profile else None
    return await service.select_microcapsules(db, activity_type)


@router.post(
    "/microcapsulas/{microcapsule_id}/finalizar",
    response_model=FinalizeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def finalizar_microcapsula(
    microcapsule_id: uuid.UUID,
    data: FinalizeRequest,
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> FinalizeResponse:
    """Registra la finalización de una microcápsula para el Usuario autenticado.

    El progreso se ancla a `current_user_id` (anti-BOLA, Req 9.6). La operación
    es idempotente: re-finalizar la misma microcápsula no la cuenta dos veces
    (Req 4.7). Al completar la ruta se habilita el enganche con Gamification y la
    Encuesta de Satisfacción (Req 4.10, 19.1, 20.1).
    """
    return await service.finalize_microcapsule(db, current_user_id, microcapsule_id, data)


@router.get("/rutas/{path_id}", response_model=PathStatusResponse)
async def estado_de_ruta(
    path_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> PathStatusResponse:
    """Devuelve el estado de la ruta y el siguiente paso adaptado del Usuario.

    El estado se consulta para el `current_user_id` autenticado; un Usuario no
    puede ver el progreso de otro (anti-BOLA, Req 9.6). La adaptación del
    siguiente paso se resuelve en backend (Req 17.3, 17.5).
    """
    return await service.get_path_status(db, current_user_id, path_id)
