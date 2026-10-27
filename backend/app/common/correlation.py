"""Gestión del Correlation-ID para trazabilidad de extremo a extremo.

Genera o propaga un identificador de correlación por petición y lo expone a
través de un `ContextVar`, de modo que el logging y las llamadas salientes
puedan adjuntarlo sin pasarlo explícitamente por cada función.
Requisito: 11.1.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_HEADER = "X-Correlation-ID"

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

    Si el cliente envía el encabezado `X-Correlation-ID`, se reutiliza; de lo
    contrario se genera un UUID v4. El valor se devuelve en la respuesta para
    permitir la trazabilidad del lado del cliente.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(CORRELATION_HEADER, "").strip()
        correlation_id = incoming or str(uuid.uuid4())
        set_correlation_id(correlation_id)
        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = correlation_id
        return response
