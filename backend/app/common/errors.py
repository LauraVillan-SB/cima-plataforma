"""Excepciones de dominio y manejadores globales de error.

Convierte errores de dominio en respuestas HTTP con mensajes genéricos en
español coloquial, incluyendo el Correlation-ID y sin exponer stack traces ni
PII al cliente. Los detalles se registran internamente.
Requisitos: 9.4, 11.2, 11.6.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.common.correlation import get_correlation_id
from app.common.logging import log_event

logger = logging.getLogger("cima.errors")


class DomainError(Exception):
    """Error de dominio base. No expone detalles sensibles al cliente."""

    status_code: int = 400
    # Mensaje genérico en español coloquial, apto para mostrar al usuario.
    public_message: str = "No pudimos procesar tu solicitud. Intenta de nuevo."

    def __init__(self, internal_detail: str | None = None) -> None:
        super().__init__(internal_detail or self.public_message)
        self.internal_detail = internal_detail or self.public_message


class ValidationError(DomainError):
    """Datos de entrada inválidos."""

    status_code = 422
    public_message = "Revisa los datos ingresados, hay algo que no está bien."


class NotFoundError(DomainError):
    """Recurso no encontrado (sin revelar si existe para otro titular)."""

    status_code = 404
    public_message = "No encontramos lo que buscas."


class ForbiddenError(DomainError):
    """Acceso no autorizado a un recurso ajeno (anti-BOLA)."""

    status_code = 403
    public_message = "No tienes permiso para ver esto."


class RateLimitedError(DomainError):
    """Se superó el límite de solicitudes permitido."""

    status_code = 429
    public_message = "Vas muy rápido. Espera un momento y vuelve a intentar."


def _error_body(message: str) -> dict[str, str]:
    """Construye el cuerpo de error genérico con el Correlation-ID."""
    return {"detail": message, "correlation_id": get_correlation_id()}


def register_error_handlers(app: FastAPI) -> None:
    """Registra los manejadores de error de dominio y el de respaldo.

    El manejador de respaldo captura cualquier excepción no prevista, registra
    el detalle internamente y devuelve un 500 genérico sin stack trace ni PII.
    """

    @app.exception_handler(DomainError)
    async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        log_event(
            logger,
            "domain_error",
            error_type=type(exc).__name__,
            detail=exc.internal_detail,
            path=request.url.path,
        )
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc.public_message))

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Detalle interno para diagnóstico; nunca se envía al cliente.
        log_event(
            logger,
            "unhandled_error",
            error_type=type(exc).__name__,
            detail=str(exc),
            path=request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content=_error_body("Tuvimos un problema de nuestro lado. Intenta más tarde."),
        )
