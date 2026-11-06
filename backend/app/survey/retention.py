"""Retención y anonimización de respuestas de encuesta (Req 20.8).

A los `data_retention_days` días desde su registro, cada respuesta de la
Encuesta de Satisfacción deja de ser vinculable a un Usuario: se rompe el
enlace con el `profile_id` (reemplazado por un marcador no identificable) y se
limpia el contenido de texto libre (`answers`), que podría contener datos
sensibles. Se conservan los campos agregables no identificables (`rating` y
`geo_zone`) para que el reporte de satisfacción por zona siga siendo posible
(Req 20.7).

Esta operación está pensada para ejecutarse como job periódico (p. ej. una
tarea programada diaria), invocando `anonimizar_respuestas_vencidas` con una
sesión de BD. Replica el patrón de `app/profile/retention.py`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.config import get_settings
from app.common.logging import log_event
from app.survey.models import SurveyResponse

logger = logging.getLogger("cima.survey.retention")

# Marcador no recuperable que sustituye el enlace con el Perfil tras anonimizar.
# No corresponde a ningún Perfil real; es un UUID fijo reservado.
ANON_PROFILE_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


def _es_anonima(response: SurveyResponse) -> bool:
    """Indica si la respuesta ya fue anonimizada (idempotencia del job)."""
    return response.profile_id == ANON_PROFILE_ID


async def anonimizar_respuestas_vencidas(
    db: AsyncSession, ahora: datetime | None = None
) -> int:
    """Anonimiza las respuestas con antigüedad ≥ retención configurada.

    Busca las respuestas cuyo `created_at` es anterior al umbral (hoy menos
    `data_retention_days`) y que aún conservan el enlace con el Perfil, rompe ese
    enlace (marcador no recuperable) y vacía el texto libre de `answers`. Conserva
    `rating` y `geo_zone` para la agregación por zona. Es idempotente: las
    respuestas ya anonimizadas no se vuelven a procesar.

    Args:
        db: Sesión de base de datos.
        ahora: Instante de referencia (inyectable para pruebas); por defecto, UTC actual.

    Returns:
        La cantidad de respuestas anonimizadas en esta ejecución.
    """
    settings = get_settings()
    referencia = ahora or datetime.now(timezone.utc)
    umbral = referencia - timedelta(days=settings.data_retention_days)

    # Consulta parametrizada vía ORM; nunca SQL concatenado.
    vencidas = await db.scalars(
        select(SurveyResponse).where(
            SurveyResponse.created_at <= umbral,
            SurveyResponse.profile_id != ANON_PROFILE_ID,
        )
    )

    anonimizadas = 0
    for response in vencidas:
        response.profile_id = ANON_PROFILE_ID
        # El texto libre podría contener datos sensibles; se descarta por completo.
        response.answers = {}
        anonimizadas += 1
        # Log sin PII: solo el identificador interno de la respuesta.
        log_event(logger, "survey_response_anonimizada", response_id=str(response.id))

    if anonimizadas:
        await db.commit()
    log_event(logger, "survey_retencion_ejecutada", anonimizadas=anonimizadas)
    return anonimizadas
