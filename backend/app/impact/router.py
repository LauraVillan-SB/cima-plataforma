"""Rutas HTTP del Tablero de Impacto ODS (`/api/v1/impacto`).

Expone el Tablero de Impacto con métricas agregadas por zona vinculadas a los
ODS. El acceso exige rol administrativo verificado en el backend (`require_admin`,
Req 15.5): un Usuario sin ese rol recibe error de autorización y el intento se
registra sin PII (Req 15.6). Las respuestas solo contienen datos agregados y
anonimizados (Req 15.3).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_session
from app.common.security import require_admin
from app.impact import service
from app.impact.dto import ImpactDashboard

router = APIRouter(prefix="/api/v1/impacto", tags=["impacto"])


@router.get("/tablero", response_model=ImpactDashboard)
async def obtener_tablero(
    db: AsyncSession = Depends(get_session),
    _admin_id: uuid.UUID = Depends(require_admin),
) -> ImpactDashboard:
    """Devuelve el Tablero de Impacto ODS; solo accesible con rol administrativo.

    `require_admin` verifica el rol en el backend antes de ejecutar la consulta
    (Req 15.5); si falla, responde error de autorización sin llegar a los datos.
    """
    return await service.build_dashboard(db)
