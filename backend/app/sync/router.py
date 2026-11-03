"""Rutas HTTP del Offline Sync Service (`/api/v1/sync`).

Expone la sincronización idempotente de la cola de acciones offline. El lote se
aplica con verificación de titularidad (anti-BOLA); las acciones repetidas por
`client_event_id` no se duplican y el progreso de ruta se fusiona sin pérdida.
Requisitos: 18.2, 18.4.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_session
from app.common.security import get_current_user_id
from app.sync import service
from app.sync.dto import SyncBatchRequest, SyncBatchResponse

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


@router.post("/acciones", response_model=SyncBatchResponse)
async def sincronizar_acciones(
    batch: SyncBatchRequest,
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> SyncBatchResponse:
    """Aplica el lote de acciones offline de forma idempotente para el Usuario."""
    return await service.apply_batch(db, current_user_id, batch)
