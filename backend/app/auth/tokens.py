"""Emisión y verificación de tokens de sesión (Req 1.10/1.11).

Tokens JWT firmados con HMAC-SHA256 usando el secreto de sesión (de config /
Secret Manager, nunca hardcodeado). Se emiten dos tipos:

- **access**: vida corta (≤ 15 min, Req 1.11) para autorizar peticiones.
- **refresh**: vida larga con rotación; cada refresco emite uno nuevo con un
  `jti` distinto, invalidando el anterior en el flujo de rotación.

El payload solo contiene identificadores no sensibles (`sub` = profile_id,
`type`, `jti`, `iss`, `exp`, `iat`). Nunca incluye PII ni la Clave.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.common.config import get_settings

_ALGORITHM = "HS256"

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


class TokenInvalidoError(Exception):
    """El token es inválido, está expirado o no es del tipo esperado.

    Es un error interno del módulo de tokens; el router lo traduce a la
    respuesta genérica de credenciales inválidas, sin exponer el detalle.
    """


def _crear_token(profile_id: uuid.UUID, token_type: str, ttl_seconds: int) -> str:
    """Firma un JWT con el tipo y TTL indicados."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(profile_id),
        "type": token_type,
        "jti": str(uuid.uuid4()),  # identificador único (rotación/revocación)
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
    }
    return jwt.encode(payload, settings.session_secret, algorithm=_ALGORITHM)


def crear_access_token(profile_id: uuid.UUID) -> str:
    """Emite un access token de vida corta (≤ 15 min, Req 1.11)."""
    return _crear_token(
        profile_id, TOKEN_TYPE_ACCESS, get_settings().access_token_ttl_seconds
    )


def crear_refresh_token(profile_id: uuid.UUID) -> str:
    """Emite un refresh token de vida larga (rotable, Req 1.11)."""
    return _crear_token(
        profile_id, TOKEN_TYPE_REFRESH, get_settings().refresh_token_ttl_seconds
    )


def decodificar_token(token: str, token_type: str) -> uuid.UUID:
    """Verifica firma, expiración y tipo; devuelve el `profile_id` (`sub`).

    :raises TokenInvalidoError: si la firma no valida, el token expiró, el tipo
        no coincide o el `sub` no es un UUID válido.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.session_secret,
            algorithms=[_ALGORITHM],
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenInvalidoError(str(exc)) from exc

    if payload.get("type") != token_type:
        raise TokenInvalidoError(
            f"expected token type {token_type}, got {payload.get('type')}"
        )
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise TokenInvalidoError("invalid sub") from exc
