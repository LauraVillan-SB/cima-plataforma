"""Registro auditable de las interacciones de IA (Req 3.9, 16.4).

Emite un único evento estructurado por interacción con: la entrada YA REDACTADA,
la salida, la versión del modelo, la decisión del guardrail y el Correlation-ID.
Excluye cualquier PII del contenido registrado (Req 3.9): la entrada ya viene
redactada (Tarea 11.2) y, por defensa en profundidad, el registro no incluye el
`profile_id` ni ningún identificador de persona, solo el id de la interacción.

El registro va al logger estructurado central (`log_event`), que además aplica
redacción de claves sensibles; nunca a archivos locales (Req 11.2).
"""

from __future__ import annotations

import logging

from app.chat.errors import RedaccionPiiError
from app.chat.models import AiInteraction
from app.chat.redaction import redactar_pii
from app.common.logging import log_event

logger = logging.getLogger("cima.chat.audit")

# Longitud máxima del contenido registrado, para evitar logs desproporcionados.
_MAX_CONTENT_CHARS = 2000

# Se registra en lugar del contenido cuando la redacción no puede completarse.
CONTENIDO_OMITIDO = "[CONTENIDO_OMITIDO]"


def registrar_auditoria(interaccion: AiInteraction) -> None:
    """Registra de forma auditable una interacción de IA ya finalizada (Req 16.4).

    Se invoca cuando la interacción queda en su estado final (listo/error). No
    persiste nada nuevo: solo emite el evento auditable al log central. El
    contenido de entrada ya está redactado; aun así se acota su longitud.

    Args:
        interaccion: la interacción a registrar, con su estado final.
    """
    log_event(
        logger,
        "chat_ai_interaction_audit",
        interaction_id=str(interaccion.id),
        status=interaccion.status,
        input_channel=interaccion.input_channel,
        input_redacted=_sin_pii(interaccion.input_redacted),
        response=_sin_pii(interaccion.response_text),
        model_version=interaccion.model_version,
        guardrail_decision=interaccion.guardrail_decision,
    )


def _sin_pii(texto: str | None) -> str | None:
    """Acota y redacta el contenido antes de registrarlo (Req 3.9, Property 40).

    La entrada ya llega redactada, pero la SALIDA viene del modelo y puede traer
    PII que el modelo generó (p. ej. un número o un correo inventados). Se redacta
    también la entrada por defensa en profundidad. Si la redacción no se completa,
    se registra `CONTENIDO_OMITIDO` en lugar del contenido.

    Args:
        texto: contenido a registrar, o None.

    Returns:
        El contenido acotado y sin PII detectable, o None si no hay contenido.
    """
    acotado = _acotar(texto)
    if acotado is None:
        return None
    try:
        return redactar_pii(acotado).texto
    except RedaccionPiiError:
        return CONTENIDO_OMITIDO


def _acotar(texto: str | None) -> str | None:
    """Acota el contenido a una longitud máxima para el registro.

    Args:
        texto: contenido a registrar (ya redactado), o None.

    Returns:
        El texto acotado a `_MAX_CONTENT_CHARS`, o None si no hay contenido.
    """
    if texto is None:
        return None
    return texto[:_MAX_CONTENT_CHARS]
