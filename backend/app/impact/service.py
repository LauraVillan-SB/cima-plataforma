"""Lógica de negocio del Tablero de Impacto ODS (Req 15).

Construye el tablero de impacto a partir de los eventos de métrica agregados por
zona y tipo, vinculando cada métrica a su ODS (Req 15.2) y aplicando la misma
supresión por k-anonimato del Metrics Service: se descartan las zonas con menos
de `K_ANONYMITY_THRESHOLD` Usuarios distintos para evitar la reidentificación
(Req 15.4). El cálculo es solo sobre datos agregados y anonimizados; no expone
PII ni identificadores individuales (Req 15.3).

El Req 15.7 (servir desde una vista precalculada vía Data Operativa/GraphQL para
no impactar los servicios operativos) es una optimización de infraestructura:
esta implementación agrega directamente con una consulta parametrizada acotada
por k-anonimato; el contrato de salida no cambia al materializar la vista.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.logging import log_event
from app.impact.constants import EVENT_TYPE_LABEL, EVENT_TYPE_TO_ODS
from app.impact.dto import ImpactDashboard, ImpactMetric
from app.metrics.constants import K_ANONYMITY_THRESHOLD, UNCLASSIFIED_ZONE
from app.metrics.models import MetricEvent

logger = logging.getLogger("cima.impact")


async def build_dashboard(db: AsyncSession) -> ImpactDashboard:
    """Construye el Tablero de Impacto agregado por zona y ODS (Req 15.1–15.4).

    Agrupa los eventos por `geo_zone` y `event_type`, cuenta eventos y Usuarios
    distintos, y suprime toda zona con menos de `K_ANONYMITY_THRESHOLD` Usuarios
    distintos (Req 15.4). Excluye los eventos sin zona clasificada ("sin_zona")
    y los tipos de evento que no tienen un ODS mapeado. No expone PII (Req 15.3).

    Args:
        db: sesión de base de datos.

    Returns:
        El tablero con las métricas agregadas que superan el k-anonimato.
    """
    distinct_users = func.count(func.distinct(MetricEvent.profile_id))
    stmt = (
        select(
            MetricEvent.geo_zone,
            MetricEvent.event_type,
            func.count(MetricEvent.id).label("total"),
            distinct_users.label("distinct_users"),
        )
        .where(MetricEvent.geo_zone != UNCLASSIFIED_ZONE)
        .group_by(MetricEvent.geo_zone, MetricEvent.event_type)
        .having(distinct_users >= K_ANONYMITY_THRESHOLD)
        .order_by(MetricEvent.geo_zone, MetricEvent.event_type)
    )
    rows = await db.execute(stmt)

    metrics: list[ImpactMetric] = []
    for row in rows:
        ods = EVENT_TYPE_TO_ODS.get(row.event_type)
        if ods is None:
            # Tipo de evento sin ODS mapeado: no aporta al tablero de impacto.
            continue
        metrics.append(
            ImpactMetric(
                event_type=row.event_type,
                label=EVENT_TYPE_LABEL.get(row.event_type, row.event_type),
                ods=ods,
                geo_zone=row.geo_zone,
                total=row.total,
                distinct_users=row.distinct_users,
            )
        )

    log_event(logger, "impact_dashboard_built", metrics=len(metrics))
    return ImpactDashboard(metrics=metrics)
