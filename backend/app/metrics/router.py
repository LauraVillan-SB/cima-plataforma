"""Rutas HTTP del Metrics Service (`/api/v1/metricas`).

Expone el registro idempotente de eventos de métrica y el reporte agregado por
zona con supresión por k-anonimato. El reporte nunca expone PII individual; la
autorización de acceso administrativo se refuerza en el Tablero ODS (Tarea 18.3)
una vez disponible el Auth Service.
Requisitos: 8.1, 8.2, 8.4, 8.5, 8.6.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_session
from app.metrics import service
from app.metrics.dto import MetricEventCreate, MetricEventResponse, MetricsReport

router = APIRouter(prefix="/api/v1/metricas", tags=["metricas"])


@router.post(
    "/eventos",
    response_model=MetricEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def registrar_evento(
    data: MetricEventCreate,
    db: AsyncSession = Depends(get_session),
) -> MetricEventResponse:
    """Registra un evento de métrica de forma idempotente por `client_event_id`."""
    return await service.record_event(db, data)


@router.get("/reportes", response_model=MetricsReport)
async def obtener_reporte(
    db: AsyncSession = Depends(get_session),
) -> MetricsReport:
    """Devuelve el reporte agregado por zona con k-anonimato (≥ 5 Usuarios)."""
    return await service.build_report(db)
