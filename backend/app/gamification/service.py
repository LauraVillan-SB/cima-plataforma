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

import hashlib
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ForbiddenError, NotFoundError, ValidationError
from app.common.logging import log_event
from app.gamification.constants import (
    BADGE_NAMES,
    DEFAULT_LEADERBOARD_SIZE,
    LEVELS,
    MAX_GRANT_ATTEMPTS,
    RECOGNITION_RULES,
    STREAK_RESET_DAYS,
    BadgeRule,
    Level,
)
from app.gamification.dto import (
    BadgeOut,
    BadgeStatusOut,
    GamificationSummary,
    Leaderboard,
    LeaderboardEntry,
    LevelOut,
    NextLevelOut,
    RecognitionGrantResult,
    RecognitionSummary,
)
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


# --------------------------------------------------------------------------- #
# Racha, nivel, resumen y ranking (extensión de experiencia no especificada en
# requirements.md). Las reglas viven en el backend (Req 19.3) y todo se ancla al
# titular autenticado (anti-BOLA); el ranking solo expone alias seudónimos.
# --------------------------------------------------------------------------- #


def _today() -> date:
    """Fecha actual en UTC; los días de la racha se cuentan en UTC."""
    return datetime.now(timezone.utc).date()


async def record_activity(
    db: AsyncSession, profile_id: uuid.UUID, today: date | None = None
) -> int:
    """Registra actividad del día y devuelve la racha vigente.

    Es atómica (`INSERT ... ON CONFLICT DO UPDATE`) e idempotente por día: repetir la
    llamada el mismo día no cambia la racha; al día siguiente la aumenta; si pasó más
    de un día, vuelve a 1. Dos peticiones concurrentes no pueden contarla dos veces.

    Args:
        db: sesión de base de datos.
        profile_id: Perfil con actividad; lo determina el servicio invocador.
        today: día a registrar (UTC); por defecto hoy. Permite probar sin reloj.

    Returns:
        Los días consecutivos de actividad, incluido el de hoy.
    """
    day = today or _today()
    yesterday = day - timedelta(days=STREAK_RESET_DAYS)
    streak = case(
        (UserPoints.last_activity_date == day, UserPoints.current_streak),
        (UserPoints.last_activity_date == yesterday, UserPoints.current_streak + 1),
        else_=1,
    )
    stmt = (
        pg_insert(UserPoints)
        .values(
            profile_id=profile_id, total_points=0, current_streak=1, last_activity_date=day
        )
        .on_conflict_do_update(
            index_elements=[UserPoints.profile_id],
            set_={"current_streak": streak, "last_activity_date": day},
        )
        .returning(UserPoints.current_streak)
    )
    current = await db.scalar(stmt)
    await db.commit()
    return int(current or 0)


def level_for(points: int) -> tuple[Level, Level | None]:
    """Nivel que corresponde a los puntos y el siguiente (None si ya es el máximo).

    Args:
        points: puntos acumulados (se acota a 0 si llegara negativo).

    Returns:
        El nivel actual y el siguiente.
    """
    safe = max(0, points)
    current = max((lv for lv in LEVELS if lv.min_points <= safe), key=lambda lv: lv.number)
    following = next((lv for lv in LEVELS if lv.number == current.number + 1), None)
    return current, following


def _level_progress_pct(points: int, current: Level, following: Level | None) -> int:
    """Porcentaje 0-100 del camino entre el nivel actual y el siguiente."""
    if following is None:
        return 100
    span = following.min_points - current.min_points
    return min(100, max(0, round((max(0, points) - current.min_points) * 100 / span)))


def _effective_streak(row: UserPoints | None, today: date) -> int:
    """Racha que se muestra: si la última actividad fue antes de ayer, ya se rompió."""
    if row is None or row.last_activity_date is None:
        return 0
    if row.last_activity_date < today - timedelta(days=STREAK_RESET_DAYS):
        return 0
    return int(row.current_streak)


async def get_summary(
    db: AsyncSession, current_user_id: uuid.UUID, today: date | None = None
) -> GamificationSummary:
    """Resumen de puntos, nivel, racha e Insignias del titular autenticado.

    Devuelve todo el catálogo de Insignias marcando cuáles ya tiene, para que el
    cliente pueda mostrar las que están en proceso. Solo lee datos del titular.

    Args:
        db: sesión de base de datos.
        current_user_id: Usuario autenticado, tomado de la sesión.
        today: día de referencia (UTC); por defecto hoy.

    Returns:
        El resumen, sin identificador del Perfil ni PII.
    """
    day = today or _today()
    row = await _get_points(db, current_user_id)
    total = row.total_points if row is not None else 0
    earned = {badge.badge_code for badge in await _list_badges(db, current_user_id)}
    current, following = level_for(total)
    return GamificationSummary(
        total_points=total,
        streak_days=_effective_streak(row, day),
        level=LevelOut(number=current.number, name=current.name, min_points=current.min_points),
        next_level=_next_level_out(total, following),
        level_progress_pct=_level_progress_pct(total, current, following),
        badges=[
            BadgeStatusOut(
                badge_code=rule.code,
                badge_name=rule.name,
                points=rule.points,
                earned=rule.code in earned,
            )
            for rule in RECOGNITION_RULES.values()
        ],
    )


def _next_level_out(points: int, following: Level | None) -> NextLevelOut | None:
    """Siguiente nivel con los puntos que faltan, o None si ya es el máximo."""
    if following is None:
        return None
    return NextLevelOut(
        number=following.number,
        name=following.name,
        points_needed=max(0, following.min_points - max(0, points)),
    )


def pseudonym(profile_id: uuid.UUID) -> str:
    """Alias estable y no reversible de un Perfil para el ranking.

    Deriva de un hash del identificador (que es un UUID aleatorio de 122 bits), por lo
    que no permite reconocer a la persona. No se usa teléfono, nombre ni zona.
    """
    digest = hashlib.sha256(profile_id.bytes).hexdigest()[:4].upper()
    return f"Participante {digest}"


def _leaderboard_entry(
    row: UserPoints, rank: int, my_id: uuid.UUID, today: date
) -> LeaderboardEntry:
    """Fila del ranking a partir de la fila de puntos (sin exponer el Perfil)."""
    current, _ = level_for(row.total_points)
    return LeaderboardEntry(
        rank=rank,
        alias=pseudonym(row.profile_id),
        total_points=row.total_points,
        level_name=current.name,
        streak_days=_effective_streak(row, today),
        is_me=row.profile_id == my_id,
    )


def _competition_ranks(points: list[int]) -> list[int]:
    """Posición con empates: quienes tienen los mismos puntos comparten posición."""
    ranks: list[int] = []
    for index, value in enumerate(points):
        ranks.append(ranks[-1] if index and value == points[index - 1] else index + 1)
    return ranks


async def get_leaderboard(
    db: AsyncSession,
    current_user_id: uuid.UUID,
    size: int = DEFAULT_LEADERBOARD_SIZE,
    today: date | None = None,
) -> Leaderboard:
    """Ranking de los N Usuarios con más puntos y la posición del titular.

    Solo participan quienes tienen puntos. Las entradas llevan alias seudónimo, nunca
    teléfono, nombre ni identificador real. El titular aparece aunque quede fuera del
    top (`me`). `size` lo acota el router; aquí se vuelve a acotar por seguridad.

    Args:
        db: sesión de base de datos.
        current_user_id: Usuario autenticado, tomado de la sesión.
        size: cuántas posiciones devolver.
        today: día de referencia (UTC) para la racha mostrada.

    Returns:
        El ranking, la fila del titular (si tiene puntos) y el total de participantes.
    """
    day = today or _today()
    limit = max(1, size)
    top = list(
        (
            await db.scalars(
                select(UserPoints)
                .where(UserPoints.total_points > 0)
                .order_by(UserPoints.total_points.desc(), UserPoints.updated_at.asc())
                .limit(limit)
            )
        ).all()
    )
    ranks = _competition_ranks([row.total_points for row in top])
    entries = [
        _leaderboard_entry(row, rank, current_user_id, day) for row, rank in zip(top, ranks)
    ]
    participants = int(
        await db.scalar(select(func.count()).select_from(UserPoints).where(UserPoints.total_points > 0))
        or 0
    )
    me = next((entry for entry in entries if entry.is_me), None)
    if me is None:
        me = await _my_entry_outside_top(db, current_user_id, day)
    return Leaderboard(entries=entries, me=me, participants=participants)


async def _my_entry_outside_top(
    db: AsyncSession, current_user_id: uuid.UUID, today: date
) -> LeaderboardEntry | None:
    """Fila del titular cuando no entra al top: su posición es 1 + quienes tienen más."""
    mine = await _get_points(db, current_user_id)
    if mine is None or mine.total_points <= 0:
        return None
    above = await db.scalar(
        select(func.count())
        .select_from(UserPoints)
        .where(UserPoints.total_points > mine.total_points)
    )
    return _leaderboard_entry(mine, int(above or 0) + 1, current_user_id, today)
