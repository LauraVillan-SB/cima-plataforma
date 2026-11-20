"""Errores de dominio del Survey Service.

Heredan de `DomainError` de `app.common.errors`, así que el manejador global los
convierte en una respuesta en español coloquial con Correlation-ID, sin stack trace.
El `internal_detail` lleva solo códigos de motivo, nunca datos del Usuario.
Requisitos: 20.1, 20.4, 20.5, 20.7.
"""

from __future__ import annotations

from app.common.errors import DomainError


class RutaNoCompletadaParaEncuestaError(DomainError):
    """La encuesta se presenta al completar la ruta (Req 20.1)."""

    status_code = 409
    public_message = (
        "La encuesta se abre cuando termine todas las lecciones de la ruta. "
        "Siga aprendiendo y luego nos cuenta qué le pareció."
    )


class EncuestaYaRespondidaError(DomainError):
    """Una sola respuesta por Usuario y ruta (Req 20.7)."""

    status_code = 409
    public_message = "Ya nos dio su opinión sobre esta ruta. ¡Gracias!"


class ComentarioConDatosPersonalesError(DomainError):
    """El comentario trae datos personales que no se pudieron quitar (Req 20.4, 20.5)."""

    status_code = 422
    public_message = (
        "Su comentario parece tener datos personales, como un número o un correo. "
        "Quítelos y vuelva a enviar."
    )
