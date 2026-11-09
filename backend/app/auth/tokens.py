"""Emisión y verificación de tokens de sesión (Req 1.10, 1.11, 1.14).

Tokens JWT firmados con HMAC-SHA256 usando el secreto de sesión (de config /
Secret Manager, nunca hardcodeado). Se emiten dos tipos:

- **access**: vida corta (≤ 15 min, Req 1.10) para autorizar peticiones.
- **refresh**: renueva la sesión. Vence a los 30 min de la última actividad
  (inactividad, Req 1.14), sin superar nunca el tope absoluto de la sesión
  contado desde el ingreso. Cada emisión lleva un `jti` distinto (rotación).

Ambos llevan `auth_time`, el instante del ingreso, que se conserva en cada
renovación para poder aplicar el tope absoluto. El payload solo contiene
identificadores no sensibles (`sub` = profile_id, `type`, `jti`, `iss`,
`auth_time`, `exp`, `iat`). Nunca incluye PII ni la Clave.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
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


class TokenExpiradoError(TokenInvalidoError):
    """El token tenía firma válida pero ya venció.

    Para el refresh token significa que la sesión pasó más de 30 min sin
    actividad (Req 1.14). Se distingue solo para el registro interno; hacia el
    cliente la respuesta es la misma que ante cualquier token inválido.
    """


@dataclass(frozen=True)
class DatosSesion:
    """Lo que se lee de un token válido: el titular y la hora de su ingreso."""

    profile_id: uuid.UUID
    auth_time: datetime


@dataclass(frozen=True)
class SesionEmitida:
    """Par de tokens recién emitido y la vida de la cookie del refresh."""

    access_token: str
    refresh_token: str
    refresh_max_age: int


def _ahora(ahora: datetime | None) -> datetime:
    return ahora if ahora is not None else datetime.now(timezone.utc)


def vida_refresh_segundos(auth_time: datetime, ahora: datetime | None = None) -> int:
    """Segundos de vida del refresh emitido en `ahora`.

    Es la ventana de inactividad (30 min), recortada para no pasar del tope
    absoluto de la sesión (`refresh_token_ttl_seconds` desde el ingreso).
    Devuelve 0 si la sesión ya alcanzó su tope.
    """
    settings = get_settings()
    momento = _ahora(ahora)
    fin_absoluto = auth_time + timedelta(seconds=settings.refresh_token_ttl_seconds)
    restante = int((fin_absoluto - momento).total_seconds())
    return max(0, min(settings.session_inactivity_seconds, restante))


def sesion_vencida(auth_time: datetime, ahora: datetime | None = None) -> bool:
    """Verdadero si la sesión alcanzó su tope absoluto y no se puede renovar."""
    return vida_refresh_segundos(auth_time, ahora) <= 0


def _crear_token(
    profile_id: uuid.UUID,
    token_type: str,
    ttl_seconds: int,
    auth_time: datetime,
    ahora: datetime,
) -> str:
    """Firma un JWT con el tipo, el TTL y la hora de ingreso indicados."""
    settings = get_settings()
    payload = {
        "sub": str(profile_id),
        "type": token_type,
        "jti": str(uuid.uuid4()),  # identificador único (rotación/revocación)
        "iss": settings.jwt_issuer,
        "auth_time": int(auth_time.timestamp()),
        "iat": ahora,
        "exp": ahora + timedelta(seconds=ttl_seconds),
    }
    return jwt.encode(payload, settings.session_secret, algorithm=_ALGORITHM)


def crear_access_token(
    profile_id: uuid.UUID,
    auth_time: datetime | None = None,
    ahora: datetime | None = None,
) -> str:
    """Emite un access token de vida corta (≤ 15 min, Req 1.10)."""
    momento = _ahora(ahora)
    return _crear_token(
        profile_id,
        TOKEN_TYPE_ACCESS,
        get_settings().access_token_ttl_seconds,
        auth_time or momento,
        momento,
    )


def crear_refresh_token(
    profile_id: uuid.UUID,
    auth_time: datetime | None = None,
    ahora: datetime | None = None,
) -> str:
    """Emite un refresh token que vence a los 30 min sin actividad (Req 1.14)."""
    momento = _ahora(ahora)
    inicio = auth_time or momento
    return _crear_token(
        profile_id,
        TOKEN_TYPE_REFRESH,
        vida_refresh_segundos(inicio, momento),
        inicio,
        momento,
    )


def emitir_sesion(
    profile_id: uuid.UUID,
    auth_time: datetime | None = None,
    ahora: datetime | None = None,
) -> SesionEmitida:
    """Emite el par access + refresh conservando la hora del ingreso.

    Sin `auth_time` se trata de un ingreso nuevo y se toma `ahora`.
    """
    momento = _ahora(ahora)
    inicio = auth_time or momento
    return SesionEmitida(
        access_token=crear_access_token(profile_id, inicio, momento),
        refresh_token=crear_refresh_token(profile_id, inicio, momento),
        refresh_max_age=vida_refresh_segundos(inicio, momento),
    )


def decodificar_sesion(token: str, token_type: str) -> DatosSesion:
    """Verifica firma, expiración y tipo; devuelve el titular y su `auth_time`.

    Un token emitido antes de existir `auth_time` usa su `iat` como respaldo.

    :raises TokenExpiradoError: si la firma es válida pero el token venció.
    :raises TokenInvalidoError: si la firma no valida, el tipo no coincide o el
        `sub` no es un UUID válido.
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
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiradoError("token expired") from exc
    except jwt.PyJWTError as exc:
        raise TokenInvalidoError(str(exc)) from exc

    if payload.get("type") != token_type:
        raise TokenInvalidoError(
            f"expected token type {token_type}, got {payload.get('type')}"
        )
    try:
        profile_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise TokenInvalidoError("invalid sub") from exc

    marca = payload.get("auth_time", payload["iat"])
    if not isinstance(marca, int):
        raise TokenInvalidoError("invalid auth_time")
    return DatosSesion(
        profile_id=profile_id,
        auth_time=datetime.fromtimestamp(marca, tz=timezone.utc),
    )


def decodificar_token(token: str, token_type: str) -> uuid.UUID:
    """Verifica el token y devuelve solo el `profile_id` (`sub`).

    :raises TokenInvalidoError: ver `decodificar_sesion`.
    """
    return decodificar_sesion(token, token_type).profile_id
