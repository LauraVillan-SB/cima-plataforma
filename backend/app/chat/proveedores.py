"""Selección del modelo del Agente Conversacional según la configuración (Tarea 11.4).

`obtener_modelo` decide qué `GenerativeModel` usa el worker. Falla hacia lo
seguro: si el proveedor configurado no puede usarse (sin key, key con formato
inválido o dominio fuera de la allowlist de SSRF), registra el motivo sin datos
sensibles y devuelve el respaldo seguro, que responde sin llamadas externas.
Así un error de configuración nunca deja al Usuario sin respuesta ni envía
datos a un destino no autorizado.
"""

from __future__ import annotations

import logging

from app.chat.gemini import GEMINI_HOST, GeminiModel
from app.chat.inference import GenerativeModel, SafeFallbackModel
from app.common.config import Settings, get_settings
from app.common.logging import log_event

logger = logging.getLogger("cima.chat")


def _dominio_permitido(settings: Settings, host: str) -> bool:
    """Indica si el host está en la allowlist de consumo externo (Req 10.4)."""
    crudo = settings.http_allowlist_domains or ""
    return host in {d.strip().lower() for d in crudo.split(",") if d.strip()}


def obtener_modelo(settings: Settings | None = None) -> GenerativeModel:
    """Devuelve el modelo configurado o, si no puede usarse, el respaldo seguro.

    Args:
        settings: configuración a usar; por defecto la de la aplicación. Las
            pruebas pasan una propia para no depender de `backend/.env`.
    """
    config = settings or get_settings()
    if config.chat_llm_provider != "gemini":
        return SafeFallbackModel()

    clave = config.gemini_api_key.get_secret_value().strip() if config.gemini_api_key else ""
    if not clave:
        log_event(logger, "chat_llm_sin_credencial", provider="gemini")
        return SafeFallbackModel()
    if not _dominio_permitido(config, GEMINI_HOST):
        log_event(logger, "chat_llm_host_no_permitido", provider="gemini", host=GEMINI_HOST)
        return SafeFallbackModel()
    try:
        return GeminiModel(
            clave,
            config.gemini_model,
            timeout_segundos=config.gemini_timeout_seconds,
            max_output_tokens=config.gemini_max_output_tokens,
        )
    except ValueError:
        # El mensaje de GeminiModel no incluye la key; aquí tampoco se registra.
        log_event(logger, "chat_llm_credencial_invalida", provider="gemini")
        return SafeFallbackModel()
