"""Rutas HTTP del Survey Service (`/api/v1/encuestas`).

Expone la presentación idempotente de la encuesta, el registro de respuestas con
validación en servidor y verificación de titularidad, y el reporte de
satisfacción agregado por zona con supresión por k-anonimato. El contenido
registrado y el reporte nunca exponen PII individual.
Requisitos: 20.1, 20.3, 20.4, 20.5, 20.6, 20.7.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_session
from app.common.security import get_current_user_id
from app.survey import service
from app.survey.dto import (
    SatisfactionReport,
    SurveyPresentation,
    SurveyResponseCreate,
    SurveyResponseResult,
)

router = APIRouter(prefix="/api/v1/encuestas", tags=["encuestas"])


@router.get("/reportes", response_model=SatisfactionReport)
async def obtener_reporte(
    db: AsyncSession = Depends(get_session),
) -> SatisfactionReport:
    """Devuelve el reporte de satisfacción por zona con k-anonimato (≥ 5)."""
    return await service.build_satisfaction_report(db)


@router.get("/{ruta_id}", response_model=SurveyPresentation)
async def presentar_encuesta(
    ruta_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> SurveyPresentation:
    """Presenta la encuesta de una ruta; marca si el Usuario ya respondió."""
    return await service.present_survey(db, ruta_id, current_user_id)


@router.post(
    "/{ruta_id}/respuestas",
    response_model=SurveyResponseResult,
    status_code=status.HTTP_201_CREATED,
)
async def registrar_respuesta(
    ruta_id: uuid.UUID,
    data: SurveyResponseCreate,
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> SurveyResponseResult:
    """Registra la respuesta validada e idempotente para la ruta y el Usuario."""
    return await service.record_response(db, ruta_id, current_user_id, data)
