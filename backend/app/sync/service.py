"""Lógica de negocio del Offline Sync Service.

Aplica un lote de acciones offline de forma idempotente por `client_event_id`
(Property 36) y fusiona el progreso de ruta conservando la unión de los pasos
completados, sin perder ninguno (Property 37). Verifica la titularidad del lote
contra el Usuario autenticado (anti-BOLA) y usa el ORM con consultas
parametrizadas (sin SQL concatenado).
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ForbiddenError
from app.common.logging import log_event
from app.sync.dto import (
    SyncAction,
    SyncActionResult,
    SyncBatchRequest,
    SyncBatchResponse,
)
from app.sync.models import SyncAction as SyncActionModel
from app.sync.models import SyncPathProgress

logger = logging.getLogger("cima.sync")


def _merge_progress(progress: SyncPathProgress, new_steps: list[str]) -> None:
    """Fusiona nuevos pasos en el progreso como unión de conjuntos (Property 37).

    El resultado contiene todos los pasos previos más los nuevos, sin duplicados
    y sin perder ninguno ya completado. Es monótono: el conjunto solo crece.
    """
    current = set(progress.completed_microcapsules or [])
    current.update(step for step in new_steps if step)
    # Orden estable para que la columna sea determinista entre sincronizaciones.
    progress.completed_microcapsules = sorted(current)


async def _apply_action(
    db: AsyncSession, profile_id: uuid.UUID, action: SyncAction
) -> None:
    """Aplica el efecto de una acción sobre el progreso de ruta, si corresponde.

    Solo las acciones que afectan el progreso (finalización de microcápsula)
    fusionan pasos; otras acciones quedan registradas por su `client_event_id`
    sin efecto de progreso. El `path_id` y los pasos se leen del payload validado.
    """
    if action.action_type != "microcapsula_finalizada":
        return

    raw_path = action.payload.get("path_id")
    microcapsule = action.payload.get("microcapsule_id")
    if not raw_path or not microcapsule:
        return
    try:
        path_id = uuid.UUID(str(raw_path))
    except ValueError:
        return

    progress = await db.scalar(
        select(SyncPathProgress).where(
            SyncPathProgress.profile_id == profile_id,
            SyncPathProgress.path_id == path_id,
        )
    )
    if progress is None:
        progress = SyncPathProgress(
            profile_id=profile_id,
            path_id=path_id,
            completed_microcapsules=[],
        )
        db.add(progress)

    _merge_progress(progress, [str(microcapsule)])


async def apply_batch(
    db: AsyncSession, current_user_id: uuid.UUID, batch: SyncBatchRequest
) -> SyncBatchResponse:
    """Aplica un lote de acciones offline de forma idempotente y segura.

    - Verifica que el lote pertenezca al Usuario autenticado (anti-BOLA); nunca
      confía en el `profile_id` del cliente.
    - Una acción cuyo `client_event_id` ya fue aplicado se omite (no duplica), lo
      que hace que reaplicar el mismo lote sea idempotente (Property 36).
    - Las acciones nuevas fusionan su efecto en el progreso de ruta (Property 37).
    """
    if batch.profile_id != current_user_id:
        log_event(
            logger,
            "sync_bola_attempt_blocked",
            actor_id=str(current_user_id),
            target_id=str(batch.profile_id),
        )
        raise ForbiddenError(internal_detail="cross-user sync batch blocked")

    results: list[SyncActionResult] = []
    applied_count = 0
    duplicate_count = 0

    for action in batch.actions:
        existing = await db.scalar(
            select(SyncActionModel.id).where(
                SyncActionModel.client_event_id == action.client_event_id
            )
        )
        if existing is not None:
            duplicate_count += 1
            results.append(
                SyncActionResult(
                    client_event_id=action.client_event_id,
                    action_type=action.action_type,
                    applied=False,
                )
            )
            continue

        db.add(
            SyncActionModel(
                client_event_id=action.client_event_id,
                profile_id=current_user_id,
                action_type=action.action_type,
                payload=action.payload,
            )
        )
        await _apply_action(db, current_user_id, action)
        applied_count += 1
        results.append(
            SyncActionResult(
                client_event_id=action.client_event_id,
                action_type=action.action_type,
                applied=True,
            )
        )

    await db.commit()
    log_event(
        logger,
        "sync_batch_applied",
        applied=applied_count,
        duplicates=duplicate_count,
    )
    return SyncBatchResponse(
        results=results,
        applied_count=applied_count,
        duplicate_count=duplicate_count,
    )
