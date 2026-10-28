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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dto import IngresoRequest, RegistroRequest, SesionResponse
from app.auth.password import hash_clave, verify_clave
from app.common.errors import CredencialesInvalidasError, ValidationError
from app.common.logging import log_event
from app.common.masking import mask_value
from app.profile.models import Profile

logger = logging.getLogger("cima.auth")

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
    profile = await db.scalar(
        select(Profile).where(Profile.phone_e164 == data.telefono)
    )

    if profile is None:
        # Verificación señuelo: iguala el costo de un verify real (anti-timing).
        verify_clave(data.clave, _DUMMY_HASH)
        log_event(logger, "auth_ingreso_fallido", motivo="telefono_no_registrado")
        raise CredencialesInvalidasError(internal_detail="phone not found")

    if not verify_clave(data.clave, profile.clave_hash):
        log_event(
            logger,
            "auth_ingreso_fallido",
            motivo="clave_incorrecta",
            profile_id=str(profile.id),
        )
        raise CredencialesInvalidasError(internal_detail="bad clave")

    log_event(logger, "auth_ingreso_exitoso", profile_id=str(profile.id))
    return SesionResponse(id=profile.id, telefono=mask_value(profile.phone_e164))
