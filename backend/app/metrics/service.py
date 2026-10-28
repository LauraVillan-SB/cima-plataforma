"""Lógica de negocio del Metrics Service.

Registra eventos de métrica de forma idempotente por `client_event_id` (Req 8.4)
y construye reportes agregados por zona aplicando supresión por k-anonimato
(Req 8.6), sin exponer PII individual (Req 8.5). Usa el ORM con consultas
parametrizadas (sin SQL concatenado).
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import log_event
from app.metrics.constants import K_ANONYMITY_THRESHOLD, UNCLASSIFIED_ZONE
from app.metrics.dto import (
    MetricEventCreate,
    MetricEventResponse,
    MetricsReport,
    ZoneAggregate,
)
from app.metrics.models import MetricEvent

logger = logging.getLogger("cima.metrics")


def _to_response(event: MetricEvent) -> MetricEventResponse:
    """Construye el DTO de salida de un evento registrado (sin PII, Req 8.5)."""
    return MetricEventResponse(
        id=event.id,
        event_type=event.event_type,
        geo_zone=event.geo_zone,
        classified=event.classified,
    )


async def record_event(db: AsyncSession, data: MetricEventCreate) -> MetricEventResponse:
    """Registra un evento de métrica de forma idempotente.

    Si ya existe un evento con el mismo `client_event_id`, se devuelve el
    registro existente sin crear un duplicado (idempotencia, Req 8.4). Los
    eventos sin zona se marcan como no clasificados con la zona "sin_zona"
    (Req 8.2).
    """
    existing = await db.scalar(
        select(MetricEvent).where(MetricEvent.client_event_id == data.client_event_id)
    )
    if existing is not None:
        log_event(logger, "metric_event_idempotent_hit", event_id=str(existing.id))
        return _to_response(existing)

    classified = data.geo_zone is not None
    event = MetricEvent(
        client_event_id=data.client_event_id,
        profile_id=data.profile_id,
        geo_zone=data.geo_zone if classified else UNCLASSIFIED_ZONE,
        event_type=data.event_type,
        classified=classified,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    log_event(
        logger,
        "metric_event_recorded",
        event_id=str(event.id),
        event_type=event.event_type,
        classified=event.classified,
    )
    return _to_response(event)


async def build_report(db: AsyncSession) -> MetricsReport:
    """Construye el reporte agregado por zona y tipo con k-anonimato.

    Agrupa por `geo_zone` y `event_type`, contando eventos y Usuarios distintos.
    Suprime toda zona con menos de `K_ANONYMITY_THRESHOLD` Usuarios distintos
    para evitar la reidentificación (Req 8.6, Property 27). El reporte no
    contiene campos identificables individuales (Req 8.5).
    """
    distinct_users = func.count(func.distinct(MetricEvent.profile_id))
    stmt = (
        select(
            MetricEvent.geo_zone,
            MetricEvent.event_type,
            func.count(MetricEvent.id).label("event_count"),
            distinct_users.label("distinct_users"),
        )
        .group_by(MetricEvent.geo_zone, MetricEvent.event_type)
        .having(distinct_users >= K_ANONYMITY_THRESHOLD)
        .order_by(MetricEvent.geo_zone, MetricEvent.event_type)
    )
    rows = await db.execute(stmt)
    aggregates = [
        ZoneAggregate(
            geo_zone=row.geo_zone,
            event_type=row.event_type,
            event_count=row.event_count,
            distinct_users=row.distinct_users,
        )
        for row in rows
    ]
    log_event(logger, "metrics_report_built", zones=len(aggregates))
    return MetricsReport(aggregates=aggregates)
