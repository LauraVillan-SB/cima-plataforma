"""Lógica de negocio del Survey Service.

Presenta la encuesta de forma idempotente (no se repite si ya fue respondida),
registra respuestas de forma idempotente por `client_event_id` y con
verificación de titularidad (anti-BOLA), y construye el reporte de satisfacción
agregado por zona aplicando supresión por k-anonimato (Req 20.7), sin exponer
PII individual. Usa el ORM con consultas parametrizadas (sin SQL concatenado).
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ForbiddenError, NotFoundError, ValidationError
from app.common.logging import log_event
from app.survey.constants import K_ANONYMITY_THRESHOLD, UNCLASSIFIED_ZONE
from app.survey.dto import (
    SatisfactionReport,
    SurveyPresentation,
    SurveyQuestion,
    SurveyResponseCreate,
    SurveyResponseResult,
    ZoneSatisfaction,
)
from app.survey.models import Survey, SurveyResponse

logger = logging.getLogger("cima.survey")


def _to_result(response: SurveyResponse) -> SurveyResponseResult:
    """Construye el DTO de salida de una respuesta registrada (sin PII, Req 20.4)."""
    return SurveyResponseResult(
        id=response.id,
        path_id=response.path_id,
        rating=response.rating,
        geo_zone=response.geo_zone,
    )


def _parse_questions(raw: dict) -> list[SurveyQuestion]:
    """Extrae las preguntas de la definición JSONB de forma tolerante."""
    items = raw.get("questions", []) if isinstance(raw, dict) else []
    questions: list[SurveyQuestion] = []
    for item in items:
        if isinstance(item, dict) and {"id", "text", "type"} <= item.keys():
            questions.append(
                SurveyQuestion(id=str(item["id"]), text=str(item["text"]), type=str(item["type"]))
            )
    return questions


async def present_survey(
    db: AsyncSession, path_id: uuid.UUID, current_user_id: uuid.UUID
) -> SurveyPresentation:
    """Presenta la encuesta de una ruta si está vigente.

    Marca `already_answered=True` si el Usuario ya respondió esa ruta, de modo
    que el cliente no la vuelva a presentar (idempotencia de presentación,
    Req 20.6). La consulta de respuesta previa se ancla al `current_user_id`.
    """
    survey = await db.scalar(
        select(Survey).where(Survey.path_id == path_id, Survey.active.is_(True))
    )
    if survey is None:
        raise NotFoundError(internal_detail=f"no active survey for path {path_id}")

    prior = await db.scalar(
        select(SurveyResponse.id).where(
            SurveyResponse.profile_id == current_user_id,
            SurveyResponse.path_id == path_id,
        )
    )
    return SurveyPresentation(
        survey_id=survey.id,
        path_id=survey.path_id,
        questions=_parse_questions(survey.questions or {}),
        already_answered=prior is not None,
    )


async def record_response(
    db: AsyncSession,
    path_id: uuid.UUID,
    current_user_id: uuid.UUID,
    data: SurveyResponseCreate,
) -> SurveyResponseResult:
    """Registra una respuesta de encuesta de forma idempotente y segura.

    - Verifica que el `profile_id` del cuerpo coincida con el Usuario autenticado
      (anti-BOLA, Req 20.5); nunca confía en el id del cliente.
    - Si ya existe una respuesta con el mismo `client_event_id`, la devuelve sin
      duplicar (idempotencia de reintentos, Req 20.6).
    - La restricción UNIQUE(profile_id, path_id) impide una segunda respuesta
      distinta para la misma ruta y Usuario (Req 20.6).
    """
    if data.profile_id != current_user_id:
        log_event(
            logger,
            "survey_bola_attempt_blocked",
            actor_id=str(current_user_id),
            target_id=str(data.profile_id),
        )
        raise ForbiddenError(internal_detail="cross-user survey response blocked")

    existing = await db.scalar(
        select(SurveyResponse).where(SurveyResponse.client_event_id == data.client_event_id)
    )
    if existing is not None:
        log_event(logger, "survey_response_idempotent_hit", response_id=str(existing.id))
        return _to_result(existing)

    already = await db.scalar(
        select(SurveyResponse.id).where(
            SurveyResponse.profile_id == current_user_id,
            SurveyResponse.path_id == path_id,
        )
    )
    if already is not None:
        raise ValidationError(internal_detail="survey already answered for this path")

    response = SurveyResponse(
        profile_id=current_user_id,
        path_id=path_id,
        rating=data.rating,
        answers=data.answers,
        geo_zone=data.geo_zone if data.geo_zone is not None else UNCLASSIFIED_ZONE,
        client_event_id=data.client_event_id,
    )
    db.add(response)
    await db.commit()
    await db.refresh(response)
    log_event(
        logger,
        "survey_response_recorded",
        response_id=str(response.id),
        rating=response.rating,
    )
    return _to_result(response)


async def build_satisfaction_report(db: AsyncSession) -> SatisfactionReport:
    """Construye el reporte de satisfacción agregado por zona con k-anonimato.

    Agrupa por `geo_zone`, contando respuestas, Usuarios distintos y promedio de
    calificación. Suprime toda zona con menos de `K_ANONYMITY_THRESHOLD`
    Usuarios distintos para evitar la reidentificación (Req 20.7). El reporte no
    contiene campos identificables individuales (Req 20.4).
    """
    distinct_users = func.count(func.distinct(SurveyResponse.profile_id))
    stmt = (
        select(
            SurveyResponse.geo_zone,
            func.count(SurveyResponse.id).label("response_count"),
            distinct_users.label("distinct_users"),
            func.avg(SurveyResponse.rating).label("average_rating"),
        )
        .group_by(SurveyResponse.geo_zone)
        .having(distinct_users >= K_ANONYMITY_THRESHOLD)
        .order_by(SurveyResponse.geo_zone)
    )
    rows = await db.execute(stmt)
    zones = [
        ZoneSatisfaction(
            geo_zone=row.geo_zone,
            response_count=row.response_count,
            distinct_users=row.distinct_users,
            average_rating=round(float(row.average_rating), 2),
        )
        for row in rows
    ]
    log_event(logger, "satisfaction_report_built", zones=len(zones))
    return SatisfactionReport(zones=zones)
