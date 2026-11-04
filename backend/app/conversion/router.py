"""Rutas HTTP del Conversion Service (`/api/v1/conversion`).

Expone la oferta de Microseguros por ruta (1–5 opciones según el Perfil) y el
registro idempotente de la intención de conversión. El titular se resuelve
desde la cookie de sesión (anti-BOLA); el cliente nunca envía `profile_id`. Las
respuestas no exponen PII.
Requisitos: 5.4, 5.5, 5.6, 5.8, 5.9.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_session
from app.common.security import get_current_user_id
from app.conversion import service
from app.conversion.dto import (
    ConversionIntentCreate,
    ConversionIntentResult,
    MicroinsuranceOffer,
)

router = APIRouter(prefix="/api/v1/conversion", tags=["conversion"])


@router.get("/microseguros/{ruta_id}", response_model=MicroinsuranceOffer)
async def ofrecer_microseguros(
    ruta_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> MicroinsuranceOffer:
    """Presenta las opciones de Microseguro del tipo de actividad del Usuario."""
    return await service.build_offer(db, ruta_id, current_user_id)


@router.post(
    "/intenciones/{ruta_id}",
    response_model=ConversionIntentResult,
    status_code=status.HTTP_201_CREATED,
)
async def registrar_intencion(
    ruta_id: uuid.UUID,
    data: ConversionIntentCreate,
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> ConversionIntentResult:
    """Registra la intención de conversión del Usuario, idempotente y sin PII."""
    return await service.record_intent(db, ruta_id, current_user_id, data)
