"""Logging estructurado en JSON con redacción de PII y Correlation-ID.

Emite logs en formato JSON hacia la salida estándar (recogida por el servicio
de logging centralizado), nunca a archivos locales. Redacta claves sensibles
para evitar fugas de PII, tokens o secretos.
Requisitos: 11.2, 9.4.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from app.common.correlation import get_correlation_id
from app.common.masking import mask_value

# Claves cuyo valor se enmascara (allowlist de campos sensibles conocidos).
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "phone",
        "phone_e164",
        "telefono",
        "clave",
        "password",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "document",
        "cedula",
        "email",
        "address",
        "direccion",
    }
)


def redact(data: dict[str, Any]) -> dict[str, Any]:
    """Devuelve una copia del diccionario con los valores sensibles enmascarados.

    No muta el diccionario original. Las claves no sensibles se conservan.
    """
    redacted: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in SENSITIVE_KEYS and isinstance(value, str):
            redacted[key] = mask_value(value)
        else:
            redacted[key] = value
    return redacted


class JsonFormatter(logging.Formatter):
    """Formateador que serializa cada registro como una línea JSON con contexto."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }
        extra = getattr(record, "context", None)
        if isinstance(extra, dict):
            payload.update(redact(extra))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """Configura el logging raíz para emitir JSON a stdout.

    Args:
        level: Nivel de log (p. ej. "INFO", "DEBUG").
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def log_event(logger: logging.Logger, message: str, **context: Any) -> None:
    """Registra un evento estructurado, redactando automáticamente la PII.

    Args:
        logger: Logger a usar.
        message: Mensaje corto y estable del evento (sin PII).
        **context: Pares clave-valor adicionales; las claves sensibles se enmascaran.
    """
    logger.info(message, extra={"context": context})
