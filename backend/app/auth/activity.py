"""Renovación de la sesión por actividad: ventana deslizante de 30 min (Req 1.14).

Cada petición que llega con un access token válido cuenta como actividad. En la
respuesta se renuevan las cookies de sesión: un access nuevo (≤ 15 min, Req 1.10)
y un refresh que vence 30 min después de esa petición, conservando la hora del
ingreso para no pasar el tope absoluto de la sesión.

Consecuencia: la sesión sigue viva mientras la persona use la app. Si pasa más de
30 min sin actividad, el refresh vence, `/api/v1/auth/refresco` lo rechaza y hay
que volver a autenticarse. Si pasan más de 15 min (pero menos de 30), el access
ya venció y el cliente renueva con `/refresco` sin pedir la Clave (Req 2.6).

No se renueva cuando la propia ruta ya gestionó las cookies (ingreso, registro,
refresco o salir) ni cuando el token es inválido. Nunca registra tokens ni PII.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.auth.cookies import ACCESS_COOKIE, set_session_cookies
from app.auth.tokens import (
    TOKEN_TYPE_ACCESS,
    TokenInvalidoError,
    decodificar_sesion,
    emitir_sesion,
    sesion_vencida,
)

_SET_COOKIE = b"set-cookie"
_PREFIJO_ACCESS = f"{ACCESS_COOKIE}=".encode()


def _respuesta_ya_gestiona_sesion(response: Response) -> bool:
    """Verdadero si la ruta ya fijó o borró la cookie de access.

    Pasa en ingreso, registro y refresco (emiten su propio par) y en salir (las
    borra). Renovar ahí pisaría lo que la ruta decidió.
    """
    return any(
        nombre == _SET_COOKIE and valor.startswith(_PREFIJO_ACCESS)
        for nombre, valor in response.raw_headers
    )


class ActividadSesionMiddleware(BaseHTTPMiddleware):
    """Renueva las cookies de sesión en cada petición autenticada (Req 1.14)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        token = request.cookies.get(ACCESS_COOKIE)
        if not token or _respuesta_ya_gestiona_sesion(response):
            return response
        try:
            datos = decodificar_sesion(token, TOKEN_TYPE_ACCESS)
        except TokenInvalidoError:
            # Token alterado o vencido: no hay actividad que renovar. La
            # dependencia de seguridad ya respondió (o responderá) 403.
            return response
        if sesion_vencida(datos.auth_time):
            # Tope absoluto alcanzado: se deja expirar para exigir un ingreso nuevo.
            return response

        sesion = emitir_sesion(datos.profile_id, datos.auth_time)
        set_session_cookies(
            response,
            access_token=sesion.access_token,
            refresh_token=sesion.refresh_token,
            refresh_max_age=sesion.refresh_max_age,
        )
        return response
