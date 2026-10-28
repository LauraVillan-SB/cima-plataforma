"""Rutas HTTP de autenticación (`/api/v1/auth`).

Expone el registro y el ingreso sin fricción (teléfono + Clave de 4 dígitos).
La validación de entrada es estricta en servidor (DTOs Pydantic) y la lógica,
incluida la indistinguibilidad del error de ingreso, reside en el service.
Requisitos: 1.2-1.7.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service
from app.auth.dto import IngresoRequest, RegistroRequest, SesionResponse
from app.common.database import get_session

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/registro", response_model=SesionResponse, status_code=status.HTTP_201_CREATED)
async def registro(
    data: RegistroRequest,
    db: AsyncSession = Depends(get_session),
) -> SesionResponse:
    """Crea una cuenta con teléfono y Clave (doble confirmación, Req 1.2-1.5)."""
    return await service.registrar(db, data)


@router.post("/ingreso", response_model=SesionResponse)
async def ingreso(
    data: IngresoRequest,
    db: AsyncSession = Depends(get_session),
) -> SesionResponse:
    """Autentica por teléfono + Clave; error genérico ante fallo (Req 1.6, 1.7)."""
    return await service.ingresar(db, data)
