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
from typing import NamedTuple

from sqlalchemy import any_, delete, literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import NotFoundError
from app.common.logging import log_event
from app.learning.constants import (
    EXPECTED_TIME_FACTOR,
    FALLBACK_TOPIC,
    GENERAL_TAG,
    MAX_DRAIN_BATCH,
    MAX_EVENT_RETRIES,
    MAX_PROFILE_PROMPTS,
    MAX_SELECTION,
    PACE_SLOW,
    PACE_STANDARD,
    YOUTUBE_EMBED_BASE_URL,
)
from app.learning.dto import (
    FinalizeRequest,
    FinalizeResponse,
    MicrocapsuleResponse,
    MicrocapsuleSelection,
    PathStatusResponse,
    VideoOut,
)
from app.learning.models import (
    LearningEventOutbox,
    LearningPath,
    Microcapsule,
    PathProgress,
    ProfileActivityPrompt,
)

logger = logging.getLogger("cima.learning")

# Espacio de nombres fijo para derivar claves de idempotencia deterministas de los
# eventos de métrica que emite este servicio (uuid5). Mantenerlo constante es lo
# que hace que un reintento produzca la misma clave y Metrics no duplique.
_METRICS_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "cima.learning.metrics")


def _microcapsule_event_id(profile_id: uuid.UUID, microcapsule_id: uuid.UUID) -> uuid.UUID:
    """Clave de idempotencia del evento `microcapsula_completada` de un Usuario.

    Es determinista por (Usuario, microcápsula): la cápsula cuenta una sola vez por
    Usuario aunque la repita o reintente, y nunca coincide con la clave del evento
    `ruta_completada` (que usa el `client_event_id` de la petición), evitando que
    Metrics descarte uno de los dos por considerarlos el mismo evento.
    """
    return uuid.uuid5(_METRICS_NAMESPACE, f"microcapsula_completada:{profile_id}:{microcapsule_id}")

# Notificación en español coloquial cuando no hay contenido para la actividad (Req 4.5).
_NOTICE_SIN_CONTENIDO = (
    "Todavía no tenemos contenido para tu actividad, así que te mostramos temas "
    "de adaptación al clima que te pueden servir."
)


def _to_video(capsule: Microcapsule) -> VideoOut | None:
    """Construye el video de apoyo de una cápsula, o None si no tiene.

    El DTO valida el formato del identificador; la dirección de incrustación la fija el
    backend con un dominio constante, no el cliente ni el dato almacenado.
    """
    if not capsule.video_id:
        return None
    return VideoOut(
        video_id=capsule.video_id,
        title=capsule.video_title or "",
        channel=capsule.video_channel or "",
        embed_url=f"{YOUTUBE_EMBED_BASE_URL}{capsule.video_id}",
    )


def _to_microcapsule_response(capsule: Microcapsule) -> MicrocapsuleResponse:
    """Construye el DTO de salida de una microcápsula (allowlist de campos)."""
    return MicrocapsuleResponse(
        id=capsule.id,
        topic=capsule.topic,
        activity_tags=list(capsule.activity_tags or []),
        duration_sec=capsule.duration_sec,
        difficulty=capsule.difficulty,
        title=capsule.title,
        summary=capsule.summary,
        paragraphs=list(capsule.paragraphs or []),
        key_points=list(capsule.key_points or []),
        video=_to_video(capsule),
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


async def _register_activity_prompt(db: AsyncSession, profile_id: uuid.UUID) -> bool:
    """Registra una solicitud de actividad y dice si el agente aún puede hacerla.

    El contador se incrementa de forma atómica (`INSERT ... ON CONFLICT DO UPDATE`) y
    solo mientras no llegue a `MAX_PROFILE_PROMPTS`: cuando el tope se alcanzó la
    cláusula `WHERE` no actualiza ninguna fila y no se devuelve nada, por lo que dos
    peticiones concurrentes no pueden superar las 3 solicitudes (Req 4.8).

    Args:
        db: sesión de base de datos.
        profile_id: Perfil autenticado; nunca un id del cliente (anti-BOLA).

    Returns:
        True si esta solicitud cuenta (aún no se agotaron las 3); False si ya se agotaron.
    """
    stmt = (
        pg_insert(ProfileActivityPrompt)
        .values(profile_id=profile_id, prompt_count=1)
        .on_conflict_do_update(
            index_elements=[ProfileActivityPrompt.profile_id],
            set_={"prompt_count": ProfileActivityPrompt.prompt_count + 1},
            where=ProfileActivityPrompt.prompt_count < MAX_PROFILE_PROMPTS,
        )
        .returning(ProfileActivityPrompt.prompt_count)
    )
    count = await db.scalar(stmt)
    await db.commit()
    return count is not None


async def select_for_user(
    db: AsyncSession, current_user_id: uuid.UUID
) -> MicrocapsuleSelection:
    """Selecciona microcápsulas para el Usuario autenticado según su Perfil.

    La actividad se resuelve en servidor desde el Perfil; nunca del cliente. Si el
    Perfil no la tiene, cuenta una solicitud al Usuario y, agotadas las 3, la
    selección deja de pedirla y entrega el tema general (Req 4.8, 4.9).

    Args:
        db: sesión de base de datos.
        current_user_id: Usuario autenticado, tomado de la sesión.

    Returns:
        La selección de microcápsulas.
    """
    # Import diferido: evita acoplar la carga de este módulo a la de `profile`.
    from app.profile.models import Profile

    profile = await db.get(Profile, current_user_id)
    activity_type = profile.activity_type if profile else None
    may_prompt = True
    if not (activity_type or "").strip():
        may_prompt = await _register_activity_prompt(db, current_user_id)
    return await select_microcapsules(db, activity_type, may_prompt=may_prompt)


async def select_microcapsules(
    db: AsyncSession, activity_type: str | None, may_prompt: bool = True
) -> MicrocapsuleSelection:
    """Selecciona microcápsulas personalizadas por la actividad del Perfil.

    - Perfil sin actividad → pide al agente solicitarla mientras `may_prompt` sea
      verdadero (Req 4.8); entrega el tema general como contenido por defecto. Con
      las 3 solicitudes agotadas (`may_prompt` falso) entrega el tema general sin
      personalización y sin volver a pedirla (Req 4.9).
    - Con actividad y coincidencias → hasta 10 cápsulas de esa actividad,
      ordenadas por relevancia y fecha (Req 4.3).
    - Con actividad pero sin coincidencias → tema general "adaptación al clima"
      y notificación de ausencia de contenido específico (Req 4.4, 4.5).
    """
    normalized = (activity_type or "").strip().lower()

    if not normalized:
        # Perfil incompleto: se solicita la actividad y se entrega el tema general
        # como comportamiento por defecto, sin personalización (Req 4.8, 4.9).
        general = await _fetch_general(db)
        log_event(logger, "learning_selection_profile_incomplete", may_prompt=may_prompt)
        return MicrocapsuleSelection(
            items=[_to_microcapsule_response(c) for c in _ordered_top(general)],
            fallback=True,
            prompt_activity=may_prompt,
            notice=_NOTICE_SIN_CONTENIDO if may_prompt else None,
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
    general = await _fetch_general(db)
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
        literal(activity_type) == any_(Microcapsule.activity_tags)
    )
    rows = await db.execute(stmt)
    return list(rows.scalars().all())


async def _fetch_general(db: AsyncSession) -> list[Microcapsule]:
    """Recupera las microcápsulas del tema general de adaptación al clima (Req 4.4, 4.9).

    Prefiere las etiquetadas como generales, para no entregar contenido de un cultivo o
    comercio ajeno. Si el catálogo aún no tiene ninguna etiquetada, cae al tema completo
    para no dejar al Usuario sin contenido. Consultas parametrizadas.
    """
    stmt = select(Microcapsule).where(
        Microcapsule.topic == FALLBACK_TOPIC,
        literal(GENERAL_TAG) == any_(Microcapsule.activity_tags),
    )
    general = list((await db.execute(stmt)).scalars().all())
    if general:
        return general
    rows = await db.execute(select(Microcapsule).where(Microcapsule.topic == FALLBACK_TOPIC))
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
    await _record_adaptation_signals(
        db, progress, microcapsule_id, data, already_done=microcapsule_id in done
    )
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
    # Se captura antes de otorgar reconocimientos: un conflicto en Gamification hace
    # rollback y expira `progress`; leerlo después exigiría una carga diferida.
    path_completed = bool(progress.completed)

    # Eventos que quedaron pendientes por fallos anteriores del Usuario (Req 4.7).
    await drain_outbox(db, current_user_id)

    # Evento `microcapsula_completada` (Req 4.6, 8.1). Se intenta en cada llamada y
    # es idempotente por una clave determinista (Usuario, cápsula): si la emisión
    # falló tras guardar el progreso, el reintento del cliente la recupera (Req 4.7)
    # sin duplicar, y repetir una cápsula no infla la métrica. Si el registro falla,
    # se reintenta hasta 3 veces y luego se conserva en la cola (Property 15).
    await _record_event_resilient(
        db,
        current_user_id,
        "microcapsula_completada",
        _microcapsule_event_id(current_user_id, microcapsule_id),
    )

    # Enganche de completitud de ruta: al pasar de no-completada a completada se
    # registra un evento de dominio `ruta_completada` (Req 4.6, 8.1). Ese evento
    # es el punto de integración que consumen Gamification (Req 19.1) y la
    # Encuesta de Satisfacción (Req 20.1). La emisión es idempotente por
    # `client_event_id` y solo ocurre en la transición (no en reintentos).
    just_completed = path_completed and not was_completed
    if just_completed:
        await _record_event_resilient(
            db, current_user_id, "ruta_completada", data.client_event_id
        )

    await _grant_recognitions(db, current_user_id, data.client_event_id, path_completed)

    log_event(
        logger,
        "microcapsule_finalized",
        path_completed=path_completed,
        completed_count=len(done),
        total_count=len(path_capsules),
        path_just_completed=just_completed,
    )
    return FinalizeResponse(
        path_id=data.path_id,
        microcapsule_id=microcapsule_id,
        path_completed=path_completed,
        completed_count=len(done),
        total_count=len(path_capsules),
    )


async def _exceeded_expected_time(
    db: AsyncSession, microcapsule_id: uuid.UUID, elapsed_seconds: int | None
) -> bool:
    """Indica si el Usuario excedió el tiempo esperado de la microcápsula (Req 17.1).

    Sin tiempo reportado no hay señal. El tiempo esperado es la duración de la
    cápsula por `EXPECTED_TIME_FACTOR`; la comparación se hace en el backend.

    Args:
        db: sesión de base de datos.
        microcapsule_id: cápsula finalizada.
        elapsed_seconds: tiempo reportado por el cliente, o None.

    Returns:
        True si el tiempo reportado supera el esperado.
    """
    if elapsed_seconds is None:
        return False
    capsule = await db.get(Microcapsule, microcapsule_id)
    if capsule is None:
        return False
    return elapsed_seconds > capsule.duration_sec * EXPECTED_TIME_FACTOR


async def _record_adaptation_signals(
    db: AsyncSession,
    progress: PathProgress,
    microcapsule_id: uuid.UUID,
    data: FinalizeRequest,
    already_done: bool,
) -> None:
    """Captura las señales de progreso de esta finalización (Req 17.1, 17.2).

    Las señales salen de la propia actividad: repetir una cápsula ya finalizada o
    exceder el tiempo esperado; no se le pide nada al Usuario. Un reintento de red de
    la misma petición (mismo `client_event_id` para esa cápsula) no cuenta como
    repetición (Req 4.7). Una finalización normal posterior devuelve el ritmo estándar.

    Args:
        db: sesión de base de datos.
        progress: progreso del Usuario autenticado sobre la ruta.
        microcapsule_id: cápsula finalizada.
        data: petición de finalización.
        already_done: si la cápsula ya estaba finalizada antes de esta llamada.
    """
    key = str(microcapsule_id)
    events = dict(progress.finalization_events or {})
    if events.get(key) == str(data.client_event_id):
        return
    events[key] = str(data.client_event_id)
    slow = await _exceeded_expected_time(db, microcapsule_id, data.elapsed_seconds)
    progress.finalization_events = events
    progress.repeat_count = (progress.repeat_count or 0) + int(already_done)
    progress.slow_count = (progress.slow_count or 0) + int(slow)
    progress.needs_simplification = already_done or slow


async def _failed_comprehension_check(
    db: AsyncSession, profile_id: uuid.UUID, path_id: uuid.UUID
) -> bool:
    """Indica si el Usuario falló la evaluación de la ruta y aún no la aprueba (Req 17.1).

    Es la comprobación de comprensión del sistema. Se lee del Assessment Service
    solo para el Usuario autenticado; una evaluación aprobada deja de ser señal.

    Args:
        db: sesión de base de datos.
        profile_id: Usuario autenticado.
        path_id: ruta evaluada.

    Returns:
        True si hay intentos y ninguno fue aprobado.
    """
    # Import diferido: Assessment ya depende de Learning; así no hay ciclo de carga.
    from app.assessment.models import AssessmentAttempt

    result = await db.scalars(
        select(AssessmentAttempt.passed).where(
            AssessmentAttempt.profile_id == profile_id,
            AssessmentAttempt.path_id == path_id,
        )
    )
    outcomes = list(result.all())
    return bool(outcomes) and not any(outcomes)


async def _record_streak(db: AsyncSession, current_user_id: uuid.UUID) -> None:
    """Cuenta el día de actividad del Usuario para su racha (extensión de Gamification).

    No es crítico: el progreso ya está guardado, así que un error de base de datos se
    registra y no hace fallar la finalización. Es idempotente por día.

    Args:
        db: sesión de base de datos.
        current_user_id: titular de la sesión; nunca un id del cliente.
    """
    # Import diferido: evita acoplar la carga de este módulo a la de gamification.
    from app.gamification.service import record_activity

    try:
        await record_activity(db, current_user_id)
    except SQLAlchemyError:
        await db.rollback()
        log_event(logger, "learning_streak_failed")


async def _grant_recognitions(
    db: AsyncSession,
    current_user_id: uuid.UUID,
    client_event_id: uuid.UUID,
    path_completed: bool,
) -> None:
    """Otorga las Insignias y puntos por la finalización (Req 19.1, 19.2).

    Se invoca en cada finalización y es idempotente (Req 19.5): la insignia de
    ruta se intenta mientras la ruta esté completa, no solo en la transición, para
    que un fallo previo se recupere con el reintento del cliente. Si Gamification
    no puede confirmar el otorgamiento (`ReconocimientoPendienteError`, Req 19.6)
    la finalización no falla: el progreso ya está guardado y se reintenta después.

    Args:
        db: sesión de base de datos.
        current_user_id: titular autenticado; nunca un id del cliente.
        client_event_id: id del evento de la petición, base de las claves derivadas.
        path_completed: si la ruta quedó completa para este Usuario.
    """
    # Import diferido: evita acoplar la carga de este módulo a la de gamification.
    from app.gamification import constants as gamification
    from app.gamification.errors import ReconocimientoPendienteError
    from app.gamification.service import grant_recognition

    await _record_streak(db, current_user_id)
    triggers = [gamification.TRIGGER_MICROCAPSULA_COMPLETADA]
    if path_completed:
        triggers.append(gamification.TRIGGER_RUTA_COMPLETADA)
    for trigger in triggers:
        try:
            await grant_recognition(
                db, current_user_id, trigger, uuid.uuid5(client_event_id, trigger)
            )
        except ReconocimientoPendienteError:
            log_event(logger, "learning_recognition_pending", trigger=trigger)


class _PendingEvent(NamedTuple):
    """Copia simple de un evento de la cola, a salvo de rollbacks de la sesión."""

    id: uuid.UUID
    profile_id: uuid.UUID
    event_type: str
    client_event_id: uuid.UUID


async def _record_event_resilient(
    db: AsyncSession,
    current_user_id: uuid.UUID,
    event_type: str,
    client_event_id: uuid.UUID,
) -> None:
    """Registra un evento con reintentos acotados y, si persiste el fallo, lo conserva.

    Hace el primer intento y hasta `MAX_EVENT_RETRIES` reintentos (nunca más de 3,
    Property 15). Entre intentos revierte la transacción fallida. Solo captura errores
    de base de datos; cualquier otro error es un defecto y se propaga. Si todos los
    intentos fallan, el evento queda en la cola para registrarlo después sin pérdida
    de datos (Req 4.7, 8.4).

    Args:
        db: sesión de base de datos.
        current_user_id: titular del evento, tomado de la sesión.
        event_type: tipo de evento de dominio.
        client_event_id: clave de idempotencia del evento.
    """
    for attempt in range(1 + MAX_EVENT_RETRIES):
        try:
            await _emit_metric_event(db, current_user_id, event_type, client_event_id)
            return
        except SQLAlchemyError:
            await db.rollback()
            log_event(logger, "learning_event_failed", event_type=event_type, attempt=attempt + 1)
    await _enqueue_event(db, current_user_id, event_type, client_event_id)


async def _enqueue_event(
    db: AsyncSession,
    profile_id: uuid.UUID,
    event_type: str,
    client_event_id: uuid.UUID,
) -> None:
    """Guarda el evento en la cola de forma idempotente por `client_event_id`.

    Si ni siquiera se puede guardar (la base de datos no responde) el error se
    propaga: la petición falla y el reintento del cliente, que es idempotente,
    vuelve a intentarlo; no se afirma haber conservado algo que no se guardó.

    Args:
        db: sesión de base de datos.
        profile_id: titular del evento.
        event_type: tipo de evento de dominio.
        client_event_id: clave de idempotencia del evento.
    """
    existing = await db.scalar(
        select(LearningEventOutbox).where(
            LearningEventOutbox.client_event_id == client_event_id
        )
    )
    if existing is None:
        db.add(
            LearningEventOutbox(
                profile_id=profile_id,
                client_event_id=client_event_id,
                event_type=event_type,
            )
        )
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
    log_event(logger, "learning_event_queued", event_type=event_type)


async def _drain_one(db: AsyncSession, pending: _PendingEvent) -> bool:
    """Intenta registrar un evento de la cola y lo borra si se registró.

    Args:
        db: sesión de base de datos.
        pending: copia del evento pendiente.

    Returns:
        True si se registró y se quitó de la cola; False si volvió a fallar.
    """
    try:
        await _emit_metric_event(
            db, pending.profile_id, pending.event_type, pending.client_event_id
        )
    except SQLAlchemyError:
        await db.rollback()
        log_event(logger, "learning_event_drain_failed", event_type=pending.event_type)
        return False
    await db.execute(delete(LearningEventOutbox).where(LearningEventOutbox.id == pending.id))
    await db.commit()
    return True


async def drain_outbox(
    db: AsyncSession,
    profile_id: uuid.UUID | None = None,
    limit: int = MAX_DRAIN_BATCH,
) -> int:
    """Reintenta registrar los eventos que quedaron pendientes en la cola (Req 4.7).

    Procesa del más antiguo al más nuevo y se detiene en el primer fallo para no
    insistir contra una base de datos caída. El registro en Metrics es idempotente,
    así que repetir un evento ya registrado no lo duplica. `FOR UPDATE SKIP LOCKED`
    evita que dos procesos tomen el mismo evento a la vez.

    Args:
        db: sesión de base de datos.
        profile_id: si se indica, solo los eventos de ese Usuario (el de la sesión);
            si es None, de todos (para un worker).
        limit: máximo de eventos por invocación.

    Returns:
        Cuántos eventos se registraron y se quitaron de la cola.
    """
    stmt = (
        select(LearningEventOutbox)
        .order_by(LearningEventOutbox.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    if profile_id is not None:
        stmt = stmt.where(LearningEventOutbox.profile_id == profile_id)
    rows = (await db.scalars(stmt)).all()
    batch = [_PendingEvent(r.id, r.profile_id, r.event_type, r.client_event_id) for r in rows]
    drained = 0
    for pending in batch:
        if not await _drain_one(db, pending):
            break
        drained += 1
    return drained


async def _emit_metric_event(
    db: AsyncSession,
    current_user_id: uuid.UUID,
    event_type: str,
    client_event_id: uuid.UUID,
) -> None:
    """Registra un evento de dominio (`microcapsula_completada` o `ruta_completada`).

    Delega en el Metrics Service, que registra el evento de forma idempotente por
    `client_event_id` (reintentos no duplican, Req 8.4) y lo asocia a la zona del
    Perfil, o a "sin_zona" si no la tiene (Req 8.2). El tipo lo valida el Metrics
    Service contra su allowlist. `ruta_completada` es el punto de integración que
    luego consumen Gamification (Req 19.1) y la Encuesta de Satisfacción
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
            event_type=event_type,
            geo_zone=geo_zone,
        ),
    )
    log_event(logger, "learning_metric_event_emitted", event_type=event_type)


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

    # Adaptación (Req 17.1, 17.2): se simplifica y se baja el ritmo de la siguiente
    # microcápsula si la última finalización fue una repetición o excedió el tiempo,
    # o si el Usuario falló la comprobación de comprensión. Sin esas señales la ruta
    # es la estándar (Req 17.5).
    simplify = bool(progress and progress.needs_simplification)
    if not simplify:
        simplify = await _failed_comprehension_check(db, current_user_id, path_id)

    log_event(
        logger,
        "path_status_built",
        completed=completed,
        completed_count=len(done),
        total_count=len(path_capsules),
        adapted=simplify,
    )
    return PathStatusResponse(
        path_id=path_id,
        completed=completed,
        completed_count=len(done),
        total_count=len(path_capsules),
        next_microcapsule_id=next_id,
        adapted=simplify,
        simplify=simplify,
        pace=PACE_SLOW if simplify else PACE_STANDARD,
    )
