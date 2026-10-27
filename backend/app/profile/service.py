"""Lógica de negocio del Perfil de Usuario.

Encapsula la creación, consulta y actualización del Perfil con autorización por
propiedad del recurso (anti-BOLA, Req 9.6) y construcción de respuestas con PII
enmascarada (Req 9.4, 9.5). Usa el ORM con consultas parametrizadas (sin SQL
concatenado).
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ForbiddenError, NotFoundError, ValidationError
from app.common.logging import log_event
from app.common.masking import mask_value
from app.profile.dto import ProfileCreate, ProfileResponse
from app.profile.models import Profile

logger = logging.getLogger("cima.profile")


def _to_response(profile: Profile) -> ProfileResponse:
    """Construye el DTO de salida enmascarando la PII (Req 9.4, 9.5)."""
    return ProfileResponse(
        id=profile.id,
        phone=mask_value(profile.phone_e164),
        activity_type=profile.activity_type,
        geo_zone=profile.geo_zone,
    )


async def create_profile(db: AsyncSession, data: ProfileCreate) -> ProfileResponse:
    """Crea un Perfil validado. Rechaza si el teléfono ya está registrado.

    La validación de formato ya ocurrió en el DTO; aquí se verifica la unicidad.
    """
    existing = await db.scalar(select(Profile).where(Profile.phone_e164 == data.phone))
    if existing is not None:
        raise ValidationError(internal_detail="phone already registered")

    profile = Profile(
        phone_e164=data.phone,
        activity_type=data.activity_type,
        geo_zone=data.geo_zone,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    log_event(logger, "profile_created", profile_id=str(profile.id))
    return _to_response(profile)


async def get_own_profile(db: AsyncSession, current_user_id: uuid.UUID) -> ProfileResponse:
    """Devuelve el Perfil del usuario autenticado.

    La consulta se ancla al `current_user_id` extraído de la sesión, por lo que
    un usuario nunca puede recuperar el Perfil de otro (anti-BOLA, Req 9.6).
    """
    profile = await db.get(Profile, current_user_id)
    if profile is None:
        raise NotFoundError(internal_detail=f"profile {current_user_id} not found")
    return _to_response(profile)


async def update_own_profile(
    db: AsyncSession,
    current_user_id: uuid.UUID,
    target_id: uuid.UUID,
    data: ProfileCreate,
) -> ProfileResponse:
    """Actualiza el Perfil propio.

    Verifica explícitamente que el recurso objetivo pertenezca al usuario
    autenticado antes de aplicar cualquier cambio (anti-BOLA, Req 9.6). Si no
    coincide, registra el intento sin PII y rechaza con error de autorización.
    """
    if target_id != current_user_id:
        log_event(
            logger,
            "bola_attempt_blocked",
            actor_id=str(current_user_id),
            target_id=str(target_id),
        )
        raise ForbiddenError(internal_detail="cross-user profile modification blocked")

    profile = await db.get(Profile, current_user_id)
    if profile is None:
        raise NotFoundError(internal_detail=f"profile {current_user_id} not found")

    profile.activity_type = data.activity_type
    profile.geo_zone = data.geo_zone
    await db.commit()
    await db.refresh(profile)
    log_event(logger, "profile_updated", profile_id=str(profile.id))
    return _to_response(profile)
