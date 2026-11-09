"""Gestión de cookies de sesión seguras (Req 1.11).

Centraliza el seteo y borrado de las cookies de sesión con los atributos de
seguridad exigidos: `HttpOnly` (no accesibles desde JS, evita robo por XSS y
mantiene los tokens fuera de localStorage), `Secure` (solo HTTPS en stage/prod)
y `SameSite` (mitiga CSRF). El `max_age` de cada cookie coincide con el TTL del
token correspondiente.
"""

from __future__ import annotations

from fastapi import Response

from app.common.config import get_settings

# Nombres de las cookies de sesión.
ACCESS_COOKIE = "cima_access"
REFRESH_COOKIE = "cima_refresh"

# La cookie de refresh se restringe a la ruta de refresco para no enviarla en
# cada petición (menor superficie de exposición).
_REFRESH_PATH = "/api/v1/auth"


def set_session_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    refresh_max_age: int | None = None,
) -> None:
    """Adjunta las cookies de access y refresh con atributos de seguridad.

    `refresh_max_age` debe coincidir con la vida del refresh emitido (la ventana
    de inactividad recortada al tope de la sesión, ver `tokens.emitir_sesion`).
    Si no se indica, se usa la ventana de inactividad completa (Req 1.14).
    """
    settings = get_settings()
    vida_refresh = (
        refresh_max_age if refresh_max_age is not None else settings.session_inactivity_seconds
    )
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        max_age=settings.access_token_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        max_age=vida_refresh,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path=_REFRESH_PATH,
    )


def clear_session_cookies(response: Response) -> None:
    """Elimina las cookies de sesión (cierre de sesión, Req 1.13)."""
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=_REFRESH_PATH)
