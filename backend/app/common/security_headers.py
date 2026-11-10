"""Cabeceras HTTP de seguridad en todas las respuestas de la API (OWASP A02/A05).

La API solo devuelve JSON, así que su política es la más estricta posible: no
carga nada (`default-src 'none'`) ni puede mostrarse dentro de un marco. La
única excepción es la documentación interactiva (`/docs`, `/redoc`), que es una
página HTML de FastAPI con un `<script>` en línea y recursos de un CDN; esas
rutas reciben una CSP acotada a exactamente lo que cargan.

Las cabeceras se fijan siempre, aunque una ruta haya puesto otras: así ninguna
ruta puede, por descuido, dejar una política más débil.

Estas cabeceras protegen las respuestas de la API. Las de la PWA (el HTML de
Angular) se fijan donde se sirve el frontend (CloudFront/servidor web), con CSP
por nonce y `microphone=(self)` para la voz; no las cubre este middleware.

Requisitos: 11.1 (diseño, tabla OWASP A05); tarea 24.1.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Política para respuestas JSON: no se carga ningún recurso ni se permite
# incrustar la respuesta en un marco.
CSP_API = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

# Política para la documentación interactiva de FastAPI (Swagger UI y ReDoc):
# sus recursos vienen de cdn.jsdelivr.net, el favicon de fastapi.tiangolo.com y
# las fuentes de ReDoc de Google Fonts. Swagger UI arranca con un <script> en
# línea, por eso 'unsafe-inline' solo en estas rutas.
CSP_DOCS = (
    "default-src 'none'; "
    "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "style-src 'self' https://cdn.jsdelivr.net https://fonts.googleapis.com 'unsafe-inline'; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' https://fastapi.tiangolo.com https://cdn.jsdelivr.net data:; "
    "connect-src 'self'; "
    "worker-src 'self' blob:; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)

RUTAS_DOCS: frozenset[str] = frozenset({"/docs", "/docs/oauth2-redirect", "/redoc"})

# Cabeceras comunes a toda respuesta. HSTS sin `preload`: entrar en la lista de
# precarga de los navegadores es un compromiso para todo el dominio y lo decide
# quien administra el dominio, no la API.
CABECERAS_BASE: dict[str, str] = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # La API no usa ninguna capacidad del navegador. CIMA no procesa pagos.
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
}


def cabeceras_para(ruta: str) -> dict[str, str]:
    """Cabeceras de seguridad que corresponden a una ruta."""
    csp = CSP_DOCS if ruta in RUTAS_DOCS else CSP_API
    return {**CABECERAS_BASE, "Content-Security-Policy": csp}


def aplicar_cabeceras(response: Response, ruta: str) -> Response:
    """Fija las cabeceras de seguridad de la ruta en la respuesta."""
    for nombre, valor in cabeceras_para(ruta).items():
        response.headers[nombre] = valor
    return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Agrega las cabeceras de seguridad a toda respuesta de la API."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        return aplicar_cabeceras(response, request.url.path)
