"""Errores de dominio del Assessment Service.

Heredan de `DomainError` de `app.common.errors`, por lo que el manejador global los
convierte en una respuesta genérica en español coloquial con Correlation-ID, sin
stack trace. El `internal_detail` lleva solo códigos de motivo, nunca datos del
Usuario. Usan 409 (Conflicto): el recurso existe, pero el estado actual del Usuario
no permite la operación.
Requisitos: 7.1, 7.3.
"""

from __future__ import annotations

from app.common.errors import DomainError


class RutaNoCompletadaError(DomainError):
    """La evaluación solo se presenta y califica al terminar todas las lecciones (Req 7.1)."""

    status_code = 409
    public_message = (
        "Primero termina todas las lecciones de la ruta y luego presentas la evaluación."
    )


class EvaluacionYaAprobadaError(DomainError):
    """La evaluación ya fue aprobada; no se vuelve a calificar (Req 7.3)."""

    status_code = 409
    public_message = "Ya aprobaste esta evaluación. No necesitas presentarla otra vez."
