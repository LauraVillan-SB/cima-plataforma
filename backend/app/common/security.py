"""Dependencias de seguridad compartidas.

Provee la identidad del usuario autenticado a los routers, validando el access
token de sesión firmado que viaja en la cookie `HttpOnly` (Req 1.10, 1.11). Si
la cookie falta o el token es inválido/expirado, rechaza con error de
autorización, sin revelar el detalle al cliente.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.cookies import ACCESS_COOKIE
from app.auth.tokens import TOKEN_TYPE_ACCESS, TokenInvalidoError, decodificar_token
from app.common.database import get_session
from app.common.errors import ForbiddenError
from app.common.logging import log_event
from app.profile.models import ROLE_ADMIN, Profile

logger = logging.getLogger("cima.security")


async def get_current_user_id(
    cima_access: Optional[str] = Cookie(default=None),
) -> uuid.UUID:
    """Resuelve el identificador del usuario autenticado desde la cookie de sesión.

    Valida firma, expiración y tipo del access token. Nunca confía en IDs del
    cliente: el identificador proviene exclusivamente del `sub` del token
    firmado por el servidor (anti-BOLA, Req 9.6).
    """
    if not cima_access:
        raise ForbiddenError(internal_detail="missing session cookie")
    try:
        return decodificar_token(cima_access, TOKEN_TYPE_ACCESS)
    except TokenInvalidoError as exc:
        raise ForbiddenError(internal_detail="invalid or expired access token") from exc


async def require_admin(
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session),
) -> uuid.UUID:
    """Exige que el Usuario autenticado tenga rol administrativo (Req 15.5, 15.6).

    La verificación del rol se hace SIEMPRE en el backend contra el Perfil del
    Usuario autenticado; nunca se confía en un rol enviado por el cliente. Si el
    Usuario no existe o no es `admin`, se rechaza con error de autorización y se
    registra el intento sin PII (solo el id interno del Perfil).

    Returns:
        El id del Usuario administrador autenticado.

    Raises:
        ForbiddenError: si el Usuario no tiene rol administrativo.
    """
    profile = await db.get(Profile, current_user_id)
    if profile is None or profile.role != ROLE_ADMIN:
        log_event(logger, "admin_access_denied", profile_id=str(current_user_id))
        raise ForbiddenError(internal_detail="administrative role required")
    return current_user_id
