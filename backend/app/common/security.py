"""Dependencias de seguridad compartidas.

Provee la identidad del usuario autenticado a los routers. En este slice de
referencia, la identidad se resuelve desde una cabecera de sesión simulada; el
Auth Service (Tarea 7) reemplazará esta implementación validando el token de
sesión firmado en la cookie HttpOnly y extrayendo el `sub` del usuario.

IMPORTANTE: esta es una implementación provisional de desarrollo. NO debe
usarse en producción tal cual; la autorización real depende de Auth Service.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Header

from app.common.errors import ForbiddenError


async def get_current_user_id(
    x_session_user: Optional[str] = Header(default=None),
) -> uuid.UUID:
    """Resuelve el identificador del usuario autenticado.

    Provisional: lee el id desde la cabecera `X-Session-User`. Rechaza si falta
    o no es un UUID válido. Será sustituida por la validación del token de Auth.
    """
    if not x_session_user:
        raise ForbiddenError(internal_detail="missing session identity")
    try:
        return uuid.UUID(x_session_user)
    except ValueError as exc:
        raise ForbiddenError(internal_detail="invalid session identity") from exc
