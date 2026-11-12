"""Gestión del Correlation-ID para trazabilidad de extremo a extremo.

Genera o propaga un identificador de correlación por petición y lo expone a
través de un `ContextVar`, de modo que el logging y las llamadas salientes
puedan adjuntarlo sin pasarlo explícitamente por cada función.
Requisito: 11.1.
"""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_HEADER = "X-Correlation-ID"

# Longitud máxima de un Correlation-ID. Debe caber en las columnas que lo
# persisten (p. ej. `ai_interactions.correlation_id`, VARCHAR(64)): uno más largo
# hacía fallar la inserción con un 500. Un UUID v4 mide 36.
CORRELATION_ID_MAX_LENGTH = 64

# Forma admitida para un Correlation-ID recibido del cliente (Zero Trust Input):
# solo caracteres seguros y longitud acotada. El valor viaja a logs, respuestas,
# llamadas a terceros y la base, así que no se reutiliza uno arbitrario o desmedido.
_ID_VALIDO = re.compile(rf"[A-Za-z0-9._:-]{{1,{CORRELATION_ID_MAX_LENGTH}}}")


def es_correlation_id_valido(valor: str) -> bool:
    """Indica si un Correlation-ID recibido puede conservarse sin cambios."""
    return _ID_VALIDO.fullmatch(valor) is not None

# Valor por defecto vacío; se asigna por petición en el middleware.
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Devuelve el Correlation-ID de la petición actual (cadena vacía si no hay)."""
    return _correlation_id.get()


def set_correlation_id(value: str) -> None:
    """Asigna el Correlation-ID de la petición actual."""
    _correlation_id.set(value)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware que propaga o genera el Correlation-ID por petición.

    Si el cliente envía un `X-Correlation-ID` con forma válida, se conserva sin
    cambios; si no envía uno, o el que envía no es válido, se genera un UUID v4.
    El valor se devuelve en la respuesta para permitir la trazabilidad del lado
    del cliente y se adjunta a las llamadas salientes (`http_client`).
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(CORRELATION_HEADER, "").strip()
        correlation_id = incoming if es_correlation_id_valido(incoming) else str(uuid.uuid4())
        set_correlation_id(correlation_id)
        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = correlation_id
        return response
