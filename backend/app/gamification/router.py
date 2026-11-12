"""Rutas HTTP del Gamification Service (`/api/v1/gamificacion`).

Expone solo la consulta de reconocimientos del titular autenticado. El
otorgamiento NO se expone: lo invoca el Learning Service dentro del backend,
porque un endpoint abierto permitiría darse reconocimientos sin completar nada
(Req 19.3). El titular se resuelve desde la cookie de sesión (anti-BOLA); si el
cliente pide el Perfil de otro Usuario, se rechaza con error de autorización.
Requisitos: 19.7, 19.8.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_session
from app.common.security import get_current_user_id
from app.gamification import service
from app.gamification.constants import DEFAULT_LEADERBOARD_SIZE, MAX_LEADERBOARD_SIZE
from app.gamification.dto import GamificationSummary, Leaderboard, RecognitionSummary

router = APIRouter(prefix="/api/v1/gamificacion", tags=["gamificacion"])


@router.get("/reconocimientos", response_model=RecognitionSummary)
async def consultar_reconocimientos(
    perfil_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> RecognitionSummary:
    """Lista las Insignias y el total de puntos del Usuario autenticado.

    `perfil_id` es opcional: si se envía y no coincide con el Usuario
    autenticado, se responde con error de autorización sin revelar datos.
    """
    return await service.get_recognitions(db, current_user_id, perfil_id)


@router.get("/resumen", response_model=GamificationSummary)
async def consultar_resumen(
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> GamificationSummary:
    """Puntos, nivel, racha e Insignias (con las pendientes) del Usuario autenticado.

    No recibe ningún identificador: el titular sale siempre de la sesión (anti-BOLA).
    Nivel y racha son una extensión de experiencia no especificada en el spec.
    """
    return await service.get_summary(db, current_user_id)


@router.get("/ranking", response_model=Leaderboard)
async def consultar_ranking(
    tamano: int = Query(default=DEFAULT_LEADERBOARD_SIZE, ge=1, le=MAX_LEADERBOARD_SIZE),
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> Leaderboard:
    """Ranking de los Usuarios con más puntos y la posición del titular autenticado.

    El tamaño se valida en el servidor (1 a 50). Las entradas llevan alias seudónimo:
    nunca teléfono, nombre ni identificador real.
    """
    return await service.get_leaderboard(db, current_user_id, tamano)
