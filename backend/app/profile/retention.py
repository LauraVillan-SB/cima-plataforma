"""Retención y anonimización de datos sensibles del Perfil (Req 9.8).

A los `data_retention_days` días desde su creación, la PII del Perfil deja de
ser recuperable: el teléfono se reemplaza por un marcador no identificable y el
hash de la Clave se limpia. El registro se conserva (otros dominios referencian
`profile_id`), pero sin PII, de modo que solo quedan datos agregables no
identificables.

Esta operación está pensada para ejecutarse como job periódico (p. ej. una tarea
programada diaria), invocando `anonimizar_perfiles_vencidos` con una sesión de BD.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.config import get_settings
from app.common.logging import log_event
from app.profile.models import Profile

logger = logging.getLogger("cima.profile.retention")

# Marcadores no recuperables que sustituyen la PII tras la anonimización.
# No corresponden a ningún teléfono ni Clave reales.
ANON_PHONE = "ANON"
ANON_CLAVE_HASH = "ANON"


def _es_anonimo(profile: Profile) -> bool:
    """Indica si el Perfil ya fue anonimizado (idempotencia del job)."""
    return profile.phone_e164 == ANON_PHONE


async def anonimizar_perfiles_vencidos(db: AsyncSession, ahora: datetime | None = None) -> int:
    """Anonimiza la PII de los Perfiles con antigüedad ≥ retención configurada.

    Busca los Perfiles cuyo `created_at` es anterior al umbral (hoy menos
    `data_retention_days`) y que aún conservan PII, y reemplaza el teléfono y el
    hash de la Clave por marcadores no recuperables. Es idempotente: los perfiles
    ya anonimizados no se vuelven a procesar.

    Args:
        db: Sesión de base de datos.
        ahora: Instante de referencia (inyectable para pruebas); por defecto, UTC actual.

    Returns:
        La cantidad de Perfiles anonimizados en esta ejecución.
    """
    settings = get_settings()
    referencia = ahora or datetime.now(timezone.utc)
    umbral = referencia - timedelta(days=settings.data_retention_days)

    # Consulta parametrizada vía ORM; nunca SQL concatenado.
    vencidos = await db.scalars(
        select(Profile).where(
            Profile.created_at <= umbral,
            Profile.phone_e164 != ANON_PHONE,
        )
    )

    anonimizados = 0
    for profile in vencidos:
        profile.phone_e164 = ANON_PHONE
        profile.clave_hash = ANON_CLAVE_HASH
        anonimizados += 1
        # Log sin PII: solo el identificador interno (no es dato sensible directo).
        log_event(logger, "profile_anonimizado", profile_id=str(profile.id))

    if anonimizados:
        await db.commit()
    log_event(logger, "retencion_ejecutada", anonimizados=anonimizados)
    return anonimizados
