"""Rutas HTTP del Perfil de Usuario (`/api/v1/perfiles`).

Expone la consulta y la actualización del propio Perfil. La autorización es
siempre de backend: las operaciones sobre "mi perfil" usan la identidad
autenticada, y la actualización verifica la propiedad del recurso (anti-BOLA).

No hay ruta de creación: el Perfil nace con el registro
(`POST /api/v1/auth/registro`), junto con el hash de la Clave. Una creación
pública aparte no podía funcionar (faltaba la Clave) y, como respondía distinto
según el teléfono ya existiera o no, permitía averiguar qué celulares tienen
cuenta, lo que contradice el error indistinguible del ingreso (Req 1.7, 9.4).
Requisitos: 1.7, 9.1, 9.4, 9.5, 9.6.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_session
from app.common.security import get_current_user_id
from app.profile import service
from app.profile.dto import ProfileResponse, ProfileUpdate

router = APIRouter(prefix="/api/v1/perfiles", tags=["perfiles"])


@router.get("/me", response_model=ProfileResponse)
async def obtener_mi_perfil(
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> ProfileResponse:
    """Devuelve el Perfil del usuario autenticado, con la PII enmascarada."""
    return await service.get_own_profile(db, current_user_id)


@router.put("/{perfil_id}", response_model=ProfileResponse)
async def actualizar_perfil(
    perfil_id: uuid.UUID,
    data: ProfileUpdate,
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> ProfileResponse:
    """Actualiza el Perfil propio (cultivo/comercio y zona); rechaza si es de otro usuario."""
    return await service.update_own_profile(db, current_user_id, perfil_id, data)
