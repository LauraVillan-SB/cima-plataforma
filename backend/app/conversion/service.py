"""Lógica de negocio del Conversion Service.

Presenta entre 1 y 5 opciones de Microseguro según el tipo de actividad del
Perfil (Req 5.4), registra la ausencia de oferta cuando no hay opciones
(Req 5.8) y registra la intención de conversión de forma idempotente y con
verificación de titularidad (anti-BOLA, Req 5.5, 5.6). CIMA no emite pólizas ni
cobra: solo guarda el interés como dato. Usa el ORM con consultas
parametrizadas (sin SQL concatenado) y no registra PII.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import NotFoundError, ValidationError
from app.common.logging import log_event
from app.conversion.constants import (
    INCENTIVE_STATUS_ENTREGADO,
    INCENTIVE_STATUS_PENDIENTE,
    MAX_INCENTIVE_DELIVERY_ATTEMPTS,
    MAX_MICROINSURANCE_OPTIONS,
    MICROINSURANCE_CATALOG,
)
from app.conversion.dto import (
    ConversionIntentCreate,
    ConversionIntentResult,
    IncentiveDeliveryRequest,
    IncentiveDeliveryResult,
    MicroinsuranceOffer,
    MicroinsuranceOptionOut,
)
from app.conversion.models import ConversionIntent, Incentive, NoOfferEvent
from app.learning.models import PathProgress
from app.profile.models import Profile

# Un canal de entrega del incentivo: devuelve True si la entrega fue exitosa.
# Se inyecta para poder simular éxito/fallo en pruebas sin un backend real. El
# canal real (p. ej. notificación/beneficio) se conecta en integración.
IncentiveDeliveryChannel = Callable[[Incentive], Awaitable[bool]]

logger = logging.getLogger("cima.conversion")


async def _get_owned_profile(db: AsyncSession, current_user_id: uuid.UUID) -> Profile:
    """Obtiene el Perfil del Usuario autenticado, anclado a su propio id (anti-BOLA).

    Args:
        db: sesión de base de datos.
        current_user_id: id del Usuario tomado del token de sesión.

    Returns:
        El Perfil del Usuario autenticado.

    Raises:
        NotFoundError: si el Perfil no existe.
    """
    profile = await db.get(Profile, current_user_id)
    if profile is None:
        raise NotFoundError(internal_detail="profile not found for current user")
    return profile


async def build_offer(
    db: AsyncSession, path_id: uuid.UUID, current_user_id: uuid.UUID
) -> MicroinsuranceOffer:
    """Construye la oferta de Microseguros para la ruta y el Usuario (Req 5.4, 5.8).

    Toma el tipo de actividad del Perfil autenticado (nunca del cliente). Si no
    hay opciones para ese tipo, registra un evento de ausencia de oferta y
    devuelve una oferta vacía para que el agente informe al Usuario (Req 5.8).
    La ausencia de tipo de actividad en el Perfil la maneja el agente antes de
    llamar a este servicio (Req 5.7).

    Args:
        db: sesión de base de datos.
        path_id: ruta de aprendizaje completada.
        current_user_id: id del Usuario autenticado.

    Returns:
        La oferta con entre 0 y `MAX_MICROINSURANCE_OPTIONS` opciones.
    """
    profile = await _get_owned_profile(db, current_user_id)
    opciones = MICROINSURANCE_CATALOG.get(profile.activity_type, [])[
        :MAX_MICROINSURANCE_OPTIONS
    ]
    if not opciones:
        await _registrar_ausencia_de_oferta(db, profile.activity_type)
        return MicroinsuranceOffer(
            path_id=path_id, activity_type=profile.activity_type, options=[]
        )
    return MicroinsuranceOffer(
        path_id=path_id,
        activity_type=profile.activity_type,
        options=[MicroinsuranceOptionOut(**opcion) for opcion in opciones],
    )


async def _registrar_ausencia_de_oferta(db: AsyncSession, activity_type: str) -> None:
    """Registra que no hubo oferta para un tipo de actividad, sin PII (Req 5.8).

    Args:
        db: sesión de base de datos.
        activity_type: tipo de cultivo o comercio solicitado.
    """
    db.add(NoOfferEvent(activity_type=activity_type))
    await db.commit()
    log_event(logger, "conversion_no_offer_recorded", activity_type=activity_type)


async def record_intent(
    db: AsyncSession,
    path_id: uuid.UUID,
    current_user_id: uuid.UUID,
    data: ConversionIntentCreate,
) -> ConversionIntentResult:
    """Registra la intención de conversión de forma idempotente y segura (Req 5.5, 5.6).

    - El titular es el Usuario autenticado; el cliente no envía `profile_id`
      (anti-BOLA, Req 5.5).
    - La opción seleccionada debe pertenecer al catálogo del tipo de actividad
      del Perfil; de lo contrario se rechaza sin registrar (Zero Trust Input).
    - Si ya existe una intención con el mismo `client_event_id`, se devuelve sin
      duplicar (idempotencia de reintentos, Req 5.6).

    Args:
        db: sesión de base de datos.
        path_id: ruta de aprendizaje completada.
        current_user_id: id del Usuario autenticado.
        data: datos validados de la intención.

    Returns:
        El resultado del registro, con `registered=True`.

    Raises:
        ValidationError: si la opción no pertenece a la oferta del Perfil.
    """
    profile = await _get_owned_profile(db, current_user_id)
    if not _opcion_valida(profile.activity_type, data.option_code):
        raise ValidationError(internal_detail="option not in catalog for activity type")

    existing = await db.scalar(
        select(ConversionIntent).where(
            ConversionIntent.client_event_id == data.client_event_id
        )
    )
    if existing is not None:
        log_event(logger, "conversion_intent_idempotent_hit", intent_id=str(existing.id))
        return _to_result(existing)

    intent = ConversionIntent(
        profile_id=current_user_id,
        path_id=path_id,
        option_code=data.option_code,
        client_event_id=data.client_event_id,
    )
    db.add(intent)
    await db.commit()
    await db.refresh(intent)
    log_event(
        logger,
        "conversion_intent_recorded",
        intent_id=str(intent.id),
        option_code=intent.option_code,
    )
    return _to_result(intent)


def _opcion_valida(activity_type: str, option_code: str) -> bool:
    """Indica si el código de opción pertenece al catálogo del tipo de actividad.

    Args:
        activity_type: tipo de cultivo o comercio del Perfil.
        option_code: código de la opción seleccionada.

    Returns:
        True si la opción existe en el catálogo de ese tipo de actividad.
    """
    opciones = MICROINSURANCE_CATALOG.get(activity_type, [])
    return any(opcion["codigo"] == option_code for opcion in opciones)


def _to_result(intent: ConversionIntent) -> ConversionIntentResult:
    """Construye el DTO de salida de una intención registrada (sin PII, Req 5.9).

    Args:
        intent: la intención persistida.

    Returns:
        El DTO de salida con `registered=True`.
    """
    return ConversionIntentResult(
        id=intent.id,
        path_id=intent.path_id,
        option_code=intent.option_code,
        registered=True,
    )


async def _default_delivery_channel(_incentive: Incentive) -> bool:
    """Canal de entrega por defecto. Placeholder hasta conectar el canal real.

    Devuelve True (entrega exitosa) para no bloquear el flujo en desarrollo. En
    integración se inyecta el canal real (notificación/beneficio), que puede
    fallar y así ejercitar la política de reintentos (Req 5.2, 5.3).
    """
    return True


async def entregar_incentivo(
    db: AsyncSession,
    path_id: uuid.UUID,
    current_user_id: uuid.UUID,
    data: IncentiveDeliveryRequest,
    delivery_channel: IncentiveDeliveryChannel | None = None,
) -> IncentiveDeliveryResult:
    """Entrega (o reintenta) el incentivo de una ruta completada (Req 5.1–5.3).

    Flujo:
    - Verifica que el Usuario autenticado haya completado al 100% la ruta
      (Req 5.1); si no, se rechaza sin crear incentivo.
    - Obtiene o crea el incentivo de forma idempotente por (profile_id, path_id):
      un incentivo ya entregado se devuelve tal cual (no se entrega dos veces).
    - Realiza UN intento de entrega por invocación (no bloquea con esperas). Si
      tiene éxito, marca `entregado`. Si falla, incrementa `retry_count` y lo
      deja `pendiente`; al alcanzar 3 intentos queda pendiente definitivo y la
      falla queda registrada por `profile_id` para resolución posterior (Req 5.3).
    - El estado de completitud de la ruta nunca se altera aquí (Req 5.2, 5.3).

    El intervalo de 5 s entre reintentos (Req 5.2) lo aplica el scheduler/worker
    que vuelve a invocar esta función, no la petición del Usuario.

    Args:
        db: sesión de base de datos.
        path_id: ruta de aprendizaje completada.
        current_user_id: id del Usuario autenticado.
        data: datos validados del disparo de entrega.
        delivery_channel: canal de entrega inyectable (por defecto, placeholder).

    Returns:
        El estado de la entrega, con la confirmación observable.

    Raises:
        ValidationError: si la ruta no está completada por el Usuario (Req 5.1).
    """
    channel = delivery_channel or _default_delivery_channel

    await _verificar_ruta_completada(db, path_id, current_user_id)

    incentive = await _get_or_create_incentive(db, path_id, current_user_id, data)

    # Si ya fue entregado, es idempotente: no se entrega de nuevo (Req 5.1).
    if incentive.delivery_status == INCENTIVE_STATUS_ENTREGADO:
        return _to_delivery_result(incentive)

    # Si ya se agotaron los intentos, permanece pendiente definitivo (Req 5.3).
    if incentive.retry_count >= MAX_INCENTIVE_DELIVERY_ATTEMPTS:
        return _to_delivery_result(incentive)

    entregado = await channel(incentive)
    if entregado:
        incentive.delivery_status = INCENTIVE_STATUS_ENTREGADO
        await db.commit()
        await db.refresh(incentive)
        log_event(
            logger,
            "incentive_delivered",
            incentive_id=str(incentive.id),
            path_id=str(incentive.path_id),
        )
        return _to_delivery_result(incentive)

    # Fallo de entrega: cuenta el intento, conserva pendiente (Req 5.2).
    incentive.retry_count += 1
    incentive.delivery_status = INCENTIVE_STATUS_PENDIENTE
    await db.commit()
    await db.refresh(incentive)

    if incentive.retry_count >= MAX_INCENTIVE_DELIVERY_ATTEMPTS:
        # Tras 3 intentos, queda pendiente definitivo; la falla se registra por
        # profile_id para resolución posterior, sin PII (Req 5.3).
        log_event(
            logger,
            "incentive_delivery_exhausted",
            incentive_id=str(incentive.id),
            profile_id=str(incentive.profile_id),
            retry_count=incentive.retry_count,
        )
    else:
        log_event(
            logger,
            "incentive_delivery_failed",
            incentive_id=str(incentive.id),
            retry_count=incentive.retry_count,
        )
    return _to_delivery_result(incentive)


async def _verificar_ruta_completada(
    db: AsyncSession, path_id: uuid.UUID, current_user_id: uuid.UUID
) -> None:
    """Valida que el Usuario autenticado completó al 100% la ruta (Req 5.1, anti-BOLA).

    La completitud la mantiene el Learning Service en `path_progress`, anclada al
    titular. Si no existe progreso completado para (profile_id, path_id), la
    entrega del incentivo no procede.
    """
    progress = await db.scalar(
        select(PathProgress).where(
            PathProgress.profile_id == current_user_id,
            PathProgress.path_id == path_id,
        )
    )
    if progress is None or not progress.completed:
        raise ValidationError(internal_detail="learning path not completed by user")


async def _get_or_create_incentive(
    db: AsyncSession,
    path_id: uuid.UUID,
    current_user_id: uuid.UUID,
    data: IncentiveDeliveryRequest,
) -> Incentive:
    """Obtiene el incentivo de la ruta para el Usuario o lo crea (idempotente).

    Idempotente por (profile_id, path_id): un segundo disparo para la misma ruta
    reutiliza el incentivo existente en lugar de crear otro.
    """
    incentive = await db.scalar(
        select(Incentive).where(
            Incentive.profile_id == current_user_id,
            Incentive.path_id == path_id,
        )
    )
    if incentive is not None:
        return incentive

    incentive = Incentive(
        profile_id=current_user_id,
        path_id=path_id,
        incentive_type=data.incentive_type,
        delivery_status=INCENTIVE_STATUS_PENDIENTE,
        retry_count=0,
    )
    db.add(incentive)
    await db.commit()
    await db.refresh(incentive)
    return incentive


def _to_delivery_result(incentive: Incentive) -> IncentiveDeliveryResult:
    """Construye el DTO de salida del estado de entrega (sin PII, Req 5.9)."""
    delivered = incentive.delivery_status == INCENTIVE_STATUS_ENTREGADO
    exhausted = (
        not delivered and incentive.retry_count >= MAX_INCENTIVE_DELIVERY_ATTEMPTS
    )
    return IncentiveDeliveryResult(
        id=incentive.id,
        path_id=incentive.path_id,
        status=incentive.delivery_status,
        delivered=delivered,
        retry_count=incentive.retry_count,
        exhausted=exhausted,
    )
