"""Errores de dominio del Gamification Service.

Heredan de `DomainError` de `app.common.errors`: el manejador global los
convierte en una respuesta genérica en español coloquial con Correlation-ID, sin
stack trace ni PII. El `internal_detail` lleva solo códigos de motivo.
"""

from __future__ import annotations

from app.common.errors import DomainError


class ReconocimientoPendienteError(DomainError):
    """El otorgamiento no se pudo completar tras los reintentos (Req 19.6).

    Quien invoca el otorgamiento (el Learning Service) debe conservar el evento
    de logro y reintentar más tarde con el MISMO `client_event_id`: el
    otorgamiento es idempotente, por lo que no se duplica ni se pierde.
    """

    status_code = 503
    public_message = (
        "Estamos registrando tu logro. Te lo mostraremos en unos momentos."
    )
