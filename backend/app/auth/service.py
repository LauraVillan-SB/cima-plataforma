"""Lógica de negocio de la autenticación sin fricción (Req 1).

Gestiona el registro de nuevos Perfiles (teléfono + Clave de 4 dígitos con
doble confirmación, Req 1.2-1.5) y el ingreso con mensaje de error
indistinguible que no revela si el teléfono está registrado (Req 1.6, 1.7).

Principios aplicados:
- Validación en servidor vía DTOs Pydantic (allowlist, formato de Clave/teléfono).
- Consultas parametrizadas vía ORM; nunca SQL concatenado.
- La Clave se almacena solo como hash con sal (Req 1.5); jamás en texto plano.
- Logs estructurados sin PII; el teléfono se enmascara automáticamente.
- Defensa anti-timing: el ingreso verifica un hash incluso si el teléfono no
  existe, para no filtrar su existencia por el tiempo de respuesta.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dto import (
    CambioClaveRequest,
    IngresoRequest,
    RegistroRequest,
    SesionResponse,
)
from app.auth.password import hash_clave, verify_clave
from app.common.config import get_settings
from app.common.errors import (
    CredencialesInvalidasError,
    CuentaBloqueadaError,
    NotFoundError,
    ValidationError,
)
from app.common.logging import log_event
from app.common.masking import mask_value
from app.profile.models import Profile

logger = logging.getLogger("cima.auth")


def _esta_bloqueado(profile: Profile, ahora: datetime) -> bool:
    """Indica si el Perfil tiene un bloqueo de ingreso vigente (Req 1.12)."""
    return profile.locked_until is not None and profile.locked_until > ahora

# Hash señuelo precomputado para igualar el costo de verificación cuando el
# teléfono no existe (defensa contra timing oracle, Req 1.7). Se calcula una
# vez al importar el módulo; su valor no corresponde a ninguna Clave real.
_DUMMY_HASH = hash_clave("0000")


async def registrar(db: AsyncSession, data: RegistroRequest) -> SesionResponse:
    """Registra un nuevo Perfil con teléfono y Clave.

    El DTO ya validó el formato de teléfono/Clave y la doble confirmación
    (Req 1.3, 1.4). Aquí se verifica que el teléfono no exista aún y se
    almacena la Clave como hash con sal (Req 1.2, 1.5).

    :raises ValidationError: si el teléfono ya está registrado.
    """
    existing = await db.scalar(
        select(Profile).where(Profile.phone_e164 == data.telefono)
    )
    if existing is not None:
        # Mensaje genérico; no se expone el teléfono en texto plano.
        raise ValidationError(internal_detail="phone already registered")

    profile = Profile(
        phone_e164=data.telefono,
        clave_hash=hash_clave(data.clave),
        # Campos de perfil mínimos pendientes de completar por el Profile Service;
        # se guardan como vacíos hasta que el Usuario los defina (Req 9.1).
        activity_type="",
        geo_zone="",
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    log_event(logger, "auth_registro_exitoso", profile_id=str(profile.id))
    return SesionResponse(id=profile.id, telefono=mask_value(profile.phone_e164))


async def ingresar(db: AsyncSession, data: IngresoRequest) -> SesionResponse:
    """Autentica a un Usuario por teléfono + Clave (Req 1.6).

    Ante teléfono inexistente o Clave incorrecta se lanza SIEMPRE la misma
    excepción (mismo código y mensaje), sin revelar cuál de los dos falló
    (Req 1.7 / Property 3). Se verifica un hash señuelo cuando el teléfono no
    existe para no filtrar su existencia por tiempo de respuesta.

    :raises CredencialesInvalidasError: si las credenciales no son válidas.
    """
    settings = get_settings()
    ahora = datetime.now(timezone.utc)
    profile = await db.scalar(
        select(Profile).where(Profile.phone_e164 == data.telefono)
    )

    if profile is None:
        # Verificación señuelo: iguala el costo de un verify real (anti-timing).
        verify_clave(data.clave, _DUMMY_HASH)
        log_event(logger, "auth_ingreso_fallido", motivo="telefono_no_registrado")
        raise CredencialesInvalidasError(internal_detail="phone not found")

    # Bloqueo vigente: rechazar sin siquiera verificar la Clave (Req 1.12).
    if _esta_bloqueado(profile, ahora):
        log_event(logger, "auth_ingreso_bloqueado", profile_id=str(profile.id))
        raise CuentaBloqueadaError(internal_detail="account temporarily locked")

    if not verify_clave(data.clave, profile.clave_hash):
        # Incrementa el contador de fallos; al alcanzar el umbral, bloquea
        # durante `lockout_seconds` (Req 1.12).
        profile.failed_attempts += 1
        if profile.failed_attempts >= settings.max_failed_attempts:
            profile.locked_until = ahora + timedelta(seconds=settings.lockout_seconds)
            log_event(logger, "auth_cuenta_bloqueada", profile_id=str(profile.id))
        await db.commit()
        log_event(
            logger,
            "auth_ingreso_fallido",
            motivo="clave_incorrecta",
            profile_id=str(profile.id),
            intentos=profile.failed_attempts,
        )
        raise CredencialesInvalidasError(internal_detail="bad clave")

    # Ingreso exitoso: reinicia el contador y limpia cualquier bloqueo (Req 1.13).
    if profile.failed_attempts != 0 or profile.locked_until is not None:
        profile.failed_attempts = 0
        profile.locked_until = None
        await db.commit()

    log_event(logger, "auth_ingreso_exitoso", profile_id=str(profile.id))
    return SesionResponse(id=profile.id, telefono=mask_value(profile.phone_e164))


async def cambiar_clave(
    db: AsyncSession, current_user_id: uuid.UUID, data: CambioClaveRequest
) -> None:
    """Cambia la Clave del Usuario autenticado, exigiendo la Clave actual (Req 1.15).

    Verifica la Clave actual antes de registrar la nueva; si no coincide, rechaza
    sin modificar nada. La nueva Clave se almacena como hash con sal (Req 1.5).

    :raises NotFoundError: si el Perfil autenticado no existe.
    :raises CredencialesInvalidasError: si la Clave actual no es válida.
    """
    profile = await db.get(Profile, current_user_id)
    if profile is None:
        raise NotFoundError(internal_detail=f"profile {current_user_id} not found")

    if not verify_clave(data.clave_actual, profile.clave_hash):
        log_event(logger, "auth_cambio_clave_fallido", profile_id=str(profile.id))
        raise CredencialesInvalidasError(internal_detail="current clave mismatch")

    profile.clave_hash = hash_clave(data.clave_nueva)
    await db.commit()
    log_event(logger, "auth_cambio_clave_exitoso", profile_id=str(profile.id))
