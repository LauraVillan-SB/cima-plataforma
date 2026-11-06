"""Lógica de negocio del Learning Service.

Cubre la selección personalizada de microcápsulas (Req 4.1–4.5, 4.9), el manejo
de perfil incompleto (Req 4.8, 4.9), la finalización idempotente de microcápsulas
con marcado de completitud de ruta (Req 4.6, 4.7, 4.10) y la adaptación del
siguiente paso por señales de progreso (Req 17.1–17.5).

Principios aplicados:
- Consultas parametrizadas vía ORM; nunca SQL concatenado.
- Autorización por propiedad: el progreso se ancla al `current_user_id` de la
  sesión; nunca se confía en un id del cliente (anti-BOLA, Req 9.6).
- Idempotencia de la finalización: `completed_microcapsules` es un conjunto, por
  lo que re-finalizar la misma microcápsula no la cuenta dos veces (Req 4.7); el
  `client_event_id` del evento correlaciona el disparo hacia Gamification/Metrics.
- Lógica de adaptación exclusivamente en backend (Req 17.3).
- Logs estructurados sin PII (Req 9.4).
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import NotFoundError
from app.common.logging import log_event
from app.learning.constants import FALLBACK_TOPIC, MAX_SELECTION
from app.learning.dto import (
    FinalizeRequest,
    FinalizeResponse,
    MicrocapsuleResponse,
    MicrocapsuleSelection,
    PathStatusResponse,
)
from app.learning.models import LearningPath, Microcapsule, PathProgress

logger = logging.getLogger("cima.learning")

# Notificación en español coloquial cuando no hay contenido para la actividad (Req 4.5).
_NOTICE_SIN_CONTENIDO = (
    "Todavía no tenemos contenido para tu actividad, así que te mostramos temas "
    "de adaptación al clima que te pueden servir."
)


def _to_microcapsule_response(capsule: Microcapsule) -> MicrocapsuleResponse:
    """Construye el DTO de salida de una microcápsula (allowlist de campos)."""
    return MicrocapsuleResponse(
        id=capsule.id,
        topic=capsule.topic,
        activity_tags=list(capsule.activity_tags or []),
        duration_sec=capsule.duration_sec,
        difficulty=capsule.difficulty,
    )


def _ordered_top(capsules: list[Microcapsule]) -> list[Microcapsule]:
    """Ordena por relevancia desc. y, ante empate, por fecha desc.; acota a 10 (Req 4.3).

    El orden se resuelve en memoria sobre el conjunto ya filtrado para mantener
    un criterio determinista e independiente del backend de base de datos.
    """
    ordered = sorted(
        capsules,
        key=lambda c: (float(c.relevance or 0), c.published_at),
        reverse=True,
    )
    return ordered[:MAX_SELECTION]


async def select_microcapsules(
    db: AsyncSession, activity_type: str | None
) -> MicrocapsuleSelection:
    """Selecciona microcápsulas personalizadas por la actividad del Perfil.

    - Perfil sin actividad → pide al agente solicitarla (Req 4.8); entrega el
      tema general como contenido por defecto mientras tanto (Req 4.9).
    - Con actividad y coincidencias → hasta 10 cápsulas de esa actividad,
      ordenadas por relevancia y fecha (Req 4.3).
    - Con actividad pero sin coincidencias → tema general "adaptación al clima"
      y notificación de ausencia de contenido específico (Req 4.4, 4.5).
    """
    normalized = (activity_type or "").strip().lower()

    if not normalized:
        # Perfil incompleto: se solicita la actividad y se entrega el tema general
        # como comportamiento por defecto, sin personalización (Req 4.8, 4.9).
        general = await _fetch_by_topic(db, FALLBACK_TOPIC)
        log_event(logger, "learning_selection_profile_incomplete")
        return MicrocapsuleSelection(
            items=[_to_microcapsule_response(c) for c in _ordered_top(general)],
            fallback=True,
            prompt_activity=True,
            notice=_NOTICE_SIN_CONTENIDO,
        )

    matches = await _fetch_by_activity(db, normalized)
    if matches:
        log_event(
            logger,
            "learning_selection_personalized",
            count=min(len(matches), MAX_SELECTION),
        )
        return MicrocapsuleSelection(
            items=[_to_microcapsule_response(c) for c in _ordered_top(matches)],
            fallback=False,
            prompt_activity=False,
            notice=None,
        )

    # Sin coincidencias para la actividad declarada → fallback al tema general.
    general = await _fetch_by_topic(db, FALLBACK_TOPIC)
    log_event(logger, "learning_selection_fallback")
    return MicrocapsuleSelection(
        items=[_to_microcapsule_response(c) for c in _ordered_top(general)],
        fallback=True,
        prompt_activity=False,
        notice=_NOTICE_SIN_CONTENIDO,
    )


async def _fetch_by_activity(db: AsyncSession, activity_type: str) -> list[Microcapsule]:
    """Recupera microcápsulas cuya `activity_tags` contiene la actividad dada."""
    stmt = select(Microcapsule).where(
        Microcapsule.activity_tags.any(activity_type)
    )
    rows = await db.execute(stmt)
    return list(rows.scalars().all())


async def _fetch_by_topic(db: AsyncSession, topic: str) -> list[Microcapsule]:
    """Recupera microcápsulas de un tema dado (consulta parametrizada)."""
    rows = await db.execute(select(Microcapsule).where(Microcapsule.topic == topic))
    return list(rows.scalars().all())


async def _get_or_create_progress(
    db: AsyncSession, current_user_id: uuid.UUID, path_id: uuid.UUID
) -> PathProgress:
    """Obtiene el progreso del Usuario sobre la ruta, creándolo si no existe.

    La búsqueda se ancla al `current_user_id` autenticado (anti-BOLA, Req 9.6):
    un Usuario nunca accede ni modifica el progreso de otro.
    """
    stmt = select(PathProgress).where(
        PathProgress.profile_id == current_user_id,
        PathProgress.path_id == path_id,
    )
    progress = await db.scalar(stmt)
    if progress is None:
        progress = PathProgress(
            profile_id=current_user_id,
            path_id=path_id,
            completed_microcapsules=[],
            completed=False,
            last_completed_step=0,
        )
        db.add(progress)
    return progress


async def finalize_microcapsule(
    db: AsyncSession,
    current_user_id: uuid.UUID,
    microcapsule_id: uuid.UUID,
    data: FinalizeRequest,
) -> FinalizeResponse:
    """Registra la finalización de una microcápsula y evalúa la completitud.

    Idempotente por conjunto: `completed_microcapsules` es un set, de modo que
    finalizar dos veces la misma microcápsula para el mismo Usuario no la cuenta
    por duplicado (Req 4.7). Cuando todas las microcápsulas de la ruta tienen
    finalización, la ruta se marca como completada (bicondicional, Req 4.10), lo
    que habilita el enganche con Gamification (Req 19.1) y la Encuesta de
    Satisfacción (Req 20.1) a través del evento de completitud correlacionado por
    `client_event_id`.
    """
    path = await db.get(LearningPath, data.path_id)
    if path is None:
        raise NotFoundError(internal_detail=f"path {data.path_id} not found")

    path_capsules: list[uuid.UUID] = list(path.microcapsule_ids or [])
    if microcapsule_id not in path_capsules:
        raise NotFoundError(
            internal_detail=f"microcapsule {microcapsule_id} not in path {data.path_id}"
        )

    progress = await _get_or_create_progress(db, current_user_id, data.path_id)

    # Estado previo: permite detectar la transición a "completada" en esta llamada
    # y emitir el evento de completitud una sola vez (no en reintentos).
    was_completed = bool(progress.completed)

    done: set[uuid.UUID] = set(progress.completed_microcapsules or [])
    if microcapsule_id not in done:
        done.add(microcapsule_id)
        progress.completed_microcapsules = list(done)
        progress.last_completed_step = max(
            progress.last_completed_step, path_capsules.index(microcapsule_id) + 1
        )

    # Completitud como bicondicional: completada sii todas las cápsulas de la
    # ruta están finalizadas para este Usuario (Req 4.10, Property 14).
    progress.completed = done.issuperset(path_capsules) and len(path_capsules) > 0

    await db.commit()
    await db.refresh(progress)

    # Enganche de completitud de ruta: al pasar de no-completada a completada se
    # registra un evento de dominio `ruta_completada` (Req 4.6, 8.1). Ese evento
    # es el punto de integración que consumen Gamification (Req 19.1) y la
    # Encuesta de Satisfacción (Req 20.1). La emisión es idempotente por
    # `client_event_id` y solo ocurre en la transición (no en reintentos).
    just_completed = progress.completed and not was_completed
    if just_completed:
        await _emit_path_completed_event(db, current_user_id, data.client_event_id)

    log_event(
        logger,
        "microcapsule_finalized",
        path_completed=progress.completed,
        completed_count=len(done),
        total_count=len(path_capsules),
        path_just_completed=just_completed,
    )
    return FinalizeResponse(
        path_id=data.path_id,
        microcapsule_id=microcapsule_id,
        path_completed=progress.completed,
        completed_count=len(done),
        total_count=len(path_capsules),
    )


async def _emit_path_completed_event(
    db: AsyncSession, current_user_id: uuid.UUID, client_event_id: uuid.UUID
) -> None:
    """Registra el evento de dominio `ruta_completada` para el Usuario (Req 4.6, 8.1).

    Delega en el Metrics Service, que registra el evento de forma idempotente por
    `client_event_id` (reintentos no duplican, Req 8.4) y lo asocia a la zona del
    Perfil, o a "sin_zona" si no la tiene (Req 8.2). Es el punto de integración
    que luego consumen Gamification (Req 19.1) y la Encuesta de Satisfacción
    (Req 20.1). La zona se resuelve en el servidor desde el Perfil; nunca del
    cliente. No se registra PII: el evento solo lleva identificadores y la zona.
    """
    # Import diferido del Metrics Service y del modelo Profile: evita acoplar la
    # carga de este módulo a la de `metrics`/`profile` y solo resuelve la
    # dependencia cuando se emite el evento.
    from app.metrics import service as metrics_service
    from app.metrics.dto import MetricEventCreate
    from app.profile.models import Profile

    profile = await db.get(Profile, current_user_id)
    geo_zone = profile.geo_zone if profile else None

    await metrics_service.record_event(
        db,
        MetricEventCreate(
            client_event_id=client_event_id,
            profile_id=current_user_id,
            event_type="ruta_completada",
            geo_zone=geo_zone,
        ),
    )
    log_event(logger, "path_completed_event_emitted")


async def get_path_status(
    db: AsyncSession, current_user_id: uuid.UUID, path_id: uuid.UUID
) -> PathStatusResponse:
    """Devuelve el estado de la ruta y el siguiente paso adaptado para el Usuario.

    La adaptación se resuelve en backend (Req 17.3) sobre las señales ya
    capturadas en el progreso; si no hay señales (sin progreso), se entrega la
    ruta estándar por defecto (Req 17.5). El contrato no cambia cuando se
    evolucione a recuperación por similitud con PgVector (Req 17.4).
    """
    path = await db.get(LearningPath, path_id)
    if path is None:
        raise NotFoundError(internal_detail=f"path {path_id} not found")

    path_capsules: list[uuid.UUID] = list(path.microcapsule_ids or [])

    stmt = select(PathProgress).where(
        PathProgress.profile_id == current_user_id,
        PathProgress.path_id == path_id,
    )
    progress = await db.scalar(stmt)

    done: set[uuid.UUID] = set(progress.completed_microcapsules or []) if progress else set()
    next_id = next((cid for cid in path_capsules if cid not in done), None)
    completed = done.issuperset(path_capsules) and len(path_capsules) > 0

    # Adaptación: hay señales si existe progreso con al menos una finalización
    # o un último paso registrado (Req 17.1, 17.2); sin señales → estándar (17.5).
    adapted = bool(progress and (done or progress.last_completed_step > 0))

    log_event(
        logger,
        "path_status_built",
        completed=completed,
        completed_count=len(done),
        total_count=len(path_capsules),
        adapted=adapted,
    )
    return PathStatusResponse(
        path_id=path_id,
        completed=completed,
        completed_count=len(done),
        total_count=len(path_capsules),
        next_microcapsule_id=next_id,
        adapted=adapted,
    )
