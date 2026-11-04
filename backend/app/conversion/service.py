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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import NotFoundError, ValidationError
from app.common.logging import log_event
from app.conversion.constants import MAX_MICROINSURANCE_OPTIONS, MICROINSURANCE_CATALOG
from app.conversion.dto import (
    ConversionIntentCreate,
    ConversionIntentResult,
    MicroinsuranceOffer,
    MicroinsuranceOptionOut,
)
from app.conversion.models import ConversionIntent, NoOfferEvent
from app.profile.models import Profile

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
