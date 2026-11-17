"""Errores de dominio del Certification Service.

Heredan de `DomainError` de `app.common.errors`, por lo que el manejador global los
convierte en una respuesta en español coloquial con Correlation-ID, sin stack trace. El
`internal_detail` lleva solo códigos de motivo, nunca datos del Usuario. Usan 409
(Conflicto), igual que el Assessment Service: la ruta existe, pero el estado actual del
Usuario todavía no permite emitir el Certificado.
Requisitos: 6.1, 6.2.
"""

from __future__ import annotations

from app.common.errors import DomainError


class RutaNoCompletadaParaCertificadoError(DomainError):
    """El Certificado solo se emite cuando la ruta está completa (Req 6.1)."""

    status_code = 409
    public_message = (
        "Para recibir tu certificado primero termina todas las lecciones de la ruta "
        "y aprueba la evaluación."
    )


class EvaluacionNoAprobadaError(DomainError):
    """No se alcanzó el puntaje mínimo de aprobación (Req 6.2)."""

    status_code = 409
    public_message = (
        "Todavía no alcanzas el puntaje mínimo de la evaluación para recibir el "
        "certificado. Repasa las lecciones y vuelve a intentarlo."
    )
