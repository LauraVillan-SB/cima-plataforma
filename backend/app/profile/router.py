"""Rutas HTTP del Perfil de Usuario (`/api/v1/perfiles`).

Expone la creación y la gestión del propio Perfil. La autorización es siempre
de backend: las operaciones sobre "mi perfil" usan la identidad autenticada, y
la actualización verifica la propiedad del recurso (anti-BOLA).
Requisitos: 9.1, 9.4, 9.5, 9.6.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_db
from app.common.security import get_current_user_id
from app.profile import service
from app.profile.dto import ProfileCreate, ProfileResponse

router = APIRouter(prefix="/api/v1/perfiles", tags=["perfiles"])


@router.post("", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def crear_perfil(
    data: ProfileCreate,
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    """Crea un Perfil de Usuario con validación estricta y allowlist de campos."""
    return await service.create_profile(db, data)


@router.get("/me", response_model=ProfileResponse)
async def obtener_mi_perfil(
    db: AsyncSession = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> ProfileResponse:
    """Devuelve el Perfil del usuario autenticado, con la PII enmascarada."""
    return await service.get_own_profile(db, current_user_id)


@router.put("/{perfil_id}", response_model=ProfileResponse)
async def actualizar_perfil(
    perfil_id: uuid.UUID,
    data: ProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> ProfileResponse:
    """Actualiza el Perfil propio; rechaza si el recurso pertenece a otro usuario."""
    return await service.update_own_profile(db, current_user_id, perfil_id, data)
