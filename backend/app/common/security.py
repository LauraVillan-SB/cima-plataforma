"""Dependencias de seguridad compartidas.

Provee la identidad del usuario autenticado a los routers, validando el access
token de sesión firmado que viaja en la cookie `HttpOnly` (Req 1.10, 1.11). Si
la cookie falta o el token es inválido/expirado, rechaza con error de
autorización, sin revelar el detalle al cliente.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Cookie

from app.auth.cookies import ACCESS_COOKIE
from app.auth.tokens import TOKEN_TYPE_ACCESS, TokenInvalidoError, decodificar_token
from app.common.errors import ForbiddenError


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
