"""Rutas HTTP del Assessment Service (`/api/v1/evaluaciones`).

Expone la presentación de la evaluación de una ruta y el envío de respuestas,
que se validan y califican en el servidor. La autorización es siempre de
backend: los intentos se anclan a la identidad autenticada (`current_user_id`),
nunca a un id del cliente (anti-BOLA).
Requisitos: 7.1–7.7.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.assessment import service
from app.assessment.dto import AnswerSubmission, AssessmentOut, AttemptResult
from app.common.database import get_session
from app.common.security import get_current_user_id

router = APIRouter(prefix="/api/v1/evaluaciones", tags=["evaluaciones"])


@router.get("/{ruta_id}", response_model=AssessmentOut)
async def obtener_evaluacion(
    ruta_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
    _current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> AssessmentOut:
    """Presenta la evaluación de la ruta, sin revelar las respuestas correctas (Req 7.1)."""
    return await service.get_assessment(db, ruta_id)


@router.post("/{ruta_id}/respuestas", response_model=AttemptResult)
async def enviar_respuestas(
    ruta_id: uuid.UUID,
    data: AnswerSubmission,
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> AttemptResult:
    """Valida y califica las respuestas de la evaluación para el Usuario autenticado.

    La validación de tipo, formato y rango ocurre en el servidor antes de
    calcular el puntaje (Req 7.6, 7.7). El intento se ancla a `current_user_id`
    (anti-BOLA, Req 9.6); los reintentos (≤ 3) y el enfriamiento de 24 h se
    controlan en el servicio (Req 7.4, 7.5).
    """
    return await service.submit_assessment(db, current_user_id, ruta_id, data)
