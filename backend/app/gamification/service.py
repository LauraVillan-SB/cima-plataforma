"""Lógica de negocio del Gamification Service.

Otorga Insignias y puntos de forma idempotente cuando un Perfil completa una
Microcápsula o una Ruta_de_Aprendizaje (Req 19.1, 19.2). Las reglas de qué se
otorga y cuántos puntos vale viven solo en el backend (`RECOGNITION_RULES`,
Req 19.3). Si el Perfil ya posee la Insignia no se duplica y los puntos no se
vuelven a sumar (Req 19.5). Ante conflictos de concurrencia reintenta hasta 3
veces y, de persistir, lanza `ReconocimientoPendienteError` para que el evento
origen se conserve y se reintente con el mismo `client_event_id` (Req 19.6).

El otorgamiento (`grant_recognition`) lo invoca el Learning Service (Tarea 13.3)
dentro del backend y NO se expone al cliente, porque permitiría darse
reconocimientos sin completar nada. La consulta (`get_recognitions`) sí se expone
al titular autenticado y rechaza el acceso a reconocimientos de otro Perfil
(Req 19.7, 19.8). Usa el ORM con consultas parametrizadas y no registra PII.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ForbiddenError, NotFoundError, ValidationError
from app.common.logging import log_event
from app.gamification.constants import (
    BADGE_NAMES,
    MAX_GRANT_ATTEMPTS,
    RECOGNITION_RULES,
    BadgeRule,
)
from app.gamification.dto import BadgeOut, RecognitionGrantResult, RecognitionSummary
from app.gamification.errors import ReconocimientoPendienteError
from app.gamification.models import UserBadge, UserPoints
from app.profile.models import Profile

logger = logging.getLogger("cima.gamification")


async def grant_recognition(
    db: AsyncSession,
    profile_id: uuid.UUID,
    trigger: str,
    client_event_id: uuid.UUID,
) -> RecognitionGrantResult:
    """Otorga el reconocimiento de un logro de forma idempotente (Req 19.1, 19.5).

    Args:
        db: sesión de base de datos.
        profile_id: Perfil que completó el logro (lo determina el servicio
            invocador, nunca el cliente).
        trigger: logro completado; debe estar en `RECOGNITION_RULES`.
        client_event_id: identificador del evento origen; los reintentos lo
            reutilizan para no duplicar el otorgamiento.

    Returns:
        El resultado con la Insignia, el total de puntos y si se otorgó ahora.

    Raises:
        ValidationError: si el logro no está en el catálogo o el
            `client_event_id` ya se usó para otro otorgamiento.
        NotFoundError: si el Perfil no existe.
        ReconocimientoPendienteError: si persisten los conflictos tras los
            reintentos; el invocador debe reintentar con el mismo evento.
    """
    rule = RECOGNITION_RULES.get(trigger)
    if rule is None:
        raise ValidationError(internal_detail="unknown recognition trigger")
    if await db.get(Profile, profile_id) is None:
        raise NotFoundError(internal_detail="profile not found for recognition")
    for attempt in range(1, MAX_GRANT_ATTEMPTS + 1):
        try:
            return await _grant_once(db, profile_id, rule, client_event_id)
        except IntegrityError:
            await db.rollback()
            log_event(logger, "gamification_grant_conflict", attempt=attempt)
    raise ReconocimientoPendienteError(internal_detail="grant conflict after max attempts")


async def _grant_once(
    db: AsyncSession,
    profile_id: uuid.UUID,
    rule: BadgeRule,
    client_event_id: uuid.UUID,
) -> RecognitionGrantResult:
    """Ejecuta un intento de otorgamiento dentro de una transacción.

    Args:
        db: sesión de base de datos.
        profile_id: Perfil que recibe el reconocimiento.
        rule: regla de la Insignia y los puntos que se otorgan.
        client_event_id: identificador del evento origen.

    Returns:
        El resultado del otorgamiento (nuevo o ya existente).

    Raises:
        ValidationError: si el `client_event_id` se reutilizó para otro otorgamiento.
        IntegrityError: ante un conflicto de concurrencia; lo reintenta el llamador.
    """
    by_event = await _find_by_event(db, client_event_id)
    if by_event is not None:
        _ensure_same_grant(by_event, profile_id, rule)
        return await _existing_result(db, profile_id, rule)
    if await _find_by_badge(db, profile_id, rule.code) is not None:
        return await _existing_result(db, profile_id, rule)

    db.add(
        UserBadge(profile_id=profile_id, badge_code=rule.code, client_event_id=client_event_id)
    )
    points = await _get_points(db, profile_id, lock=True)
    if points is None:
        points = UserPoints(profile_id=profile_id, total_points=0)
        db.add(points)
    points.total_points += rule.points
    await db.commit()
    log_event(
        logger,
        "gamification_recognition_awarded",
        badge_code=rule.code,
        points=rule.points,
    )
    return RecognitionGrantResult(
        badge_code=rule.code,
        badge_name=rule.name,
        total_points=points.total_points,
        newly_awarded=True,
    )


def _ensure_same_grant(existing: UserBadge, profile_id: uuid.UUID, rule: BadgeRule) -> None:
    """Verifica que un `client_event_id` repetido corresponda al mismo otorgamiento.

    Args:
        existing: Insignia ya registrada con ese `client_event_id`.
        profile_id: Perfil de la solicitud actual.
        rule: regla de la solicitud actual.

    Raises:
        ValidationError: si el evento se reutiliza para otro Perfil u otra Insignia.
    """
    if existing.profile_id != profile_id or existing.badge_code != rule.code:
        raise ValidationError(internal_detail="client_event_id reused for another grant")


async def _existing_result(
    db: AsyncSession, profile_id: uuid.UUID, rule: BadgeRule
) -> RecognitionGrantResult:
    """Construye el resultado de una Insignia ya otorgada, sin sumar puntos (Req 19.5).

    Args:
        db: sesión de base de datos.
        profile_id: Perfil titular de la Insignia.
        rule: regla de la Insignia ya existente.

    Returns:
        El resultado con `newly_awarded=False` y el total de puntos actual.
    """
    points = await _get_points(db, profile_id)
    log_event(logger, "gamification_idempotent_hit", badge_code=rule.code)
    return RecognitionGrantResult(
        badge_code=rule.code,
        badge_name=rule.name,
        total_points=points.total_points if points is not None else 0,
        newly_awarded=False,
    )


async def _find_by_event(db: AsyncSession, client_event_id: uuid.UUID) -> UserBadge | None:
    """Busca una Insignia por el `client_event_id` del evento origen.

    Args:
        db: sesión de base de datos.
        client_event_id: identificador del evento origen.

    Returns:
        La Insignia registrada con ese evento, o None.
    """
    return await db.scalar(
        select(UserBadge).where(UserBadge.client_event_id == client_event_id)
    )


async def _find_by_badge(
    db: AsyncSession, profile_id: uuid.UUID, badge_code: str
) -> UserBadge | None:
    """Busca una Insignia específica de un Perfil.

    Args:
        db: sesión de base de datos.
        profile_id: Perfil titular.
        badge_code: código de la Insignia.

    Returns:
        La Insignia del Perfil, o None si aún no la tiene.
    """
    return await db.scalar(
        select(UserBadge).where(
            UserBadge.profile_id == profile_id, UserBadge.badge_code == badge_code
        )
    )


async def _get_points(
    db: AsyncSession, profile_id: uuid.UUID, lock: bool = False
) -> UserPoints | None:
    """Obtiene el total de puntos de un Perfil, con bloqueo de fila opcional.

    Args:
        db: sesión de base de datos.
        profile_id: Perfil titular.
        lock: si es True, bloquea la fila (`FOR UPDATE`) para sumar sin perder
            actualizaciones concurrentes.

    Returns:
        La fila de puntos del Perfil, o None si aún no existe.
    """
    stmt = select(UserPoints).where(UserPoints.profile_id == profile_id)
    if lock:
        stmt = stmt.with_for_update()
    return await db.scalar(stmt)


async def get_recognitions(
    db: AsyncSession,
    current_user_id: uuid.UUID,
    requested_profile_id: uuid.UUID | None = None,
) -> RecognitionSummary:
    """Lista las Insignias y el total de puntos del titular autenticado (Req 19.7).

    Solo devuelve datos del Usuario autenticado. Si se pide el reconocimiento de
    otro Perfil se rechaza antes de consultar la base de datos, por lo que la
    respuesta es la misma exista o no ese Perfil (Req 19.8).

    Args:
        db: sesión de base de datos.
        current_user_id: Usuario autenticado, tomado del token de sesión.
        requested_profile_id: Perfil solicitado por el cliente, si lo indicó; solo
            se acepta si coincide con el Usuario autenticado.

    Returns:
        Las Insignias y el total de puntos del titular, sin PII.

    Raises:
        ForbiddenError: si el Perfil solicitado no es el del Usuario autenticado.
    """
    _ensure_own_profile(current_user_id, requested_profile_id)
    badges = await _list_badges(db, current_user_id)
    points = await _get_points(db, current_user_id)
    return RecognitionSummary(
        badges=[
            BadgeOut(
                badge_code=badge.badge_code,
                badge_name=BADGE_NAMES.get(badge.badge_code, badge.badge_code),
            )
            for badge in badges
        ],
        total_points=points.total_points if points is not None else 0,
    )


def _ensure_own_profile(
    current_user_id: uuid.UUID, requested_profile_id: uuid.UUID | None
) -> None:
    """Rechaza el acceso a reconocimientos de otro Perfil y registra el intento (Req 19.8).

    Args:
        current_user_id: Usuario autenticado.
        requested_profile_id: Perfil solicitado por el cliente, o None si no indicó.

    Raises:
        ForbiddenError: si el Perfil solicitado es distinto del autenticado.
    """
    if requested_profile_id is None or requested_profile_id == current_user_id:
        return
    log_event(
        logger,
        "gamification_bola_attempt_blocked",
        actor_id=str(current_user_id),
        target_id=str(requested_profile_id),
    )
    raise ForbiddenError(internal_detail="cross-user recognitions access blocked")


async def _list_badges(db: AsyncSession, profile_id: uuid.UUID) -> list[UserBadge]:
    """Lista las Insignias de un Perfil en el orden en que se otorgaron.

    Args:
        db: sesión de base de datos.
        profile_id: Perfil titular.

    Returns:
        Las Insignias del Perfil, de la más antigua a la más reciente.
    """
    result = await db.scalars(
        select(UserBadge)
        .where(UserBadge.profile_id == profile_id)
        .order_by(UserBadge.awarded_at)
    )
    return list(result.all())
