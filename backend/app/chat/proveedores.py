"""Selección de los proveedores del Agente Conversacional según la configuración.

`obtener_modelo` decide qué `GenerativeModel` usa el worker y `obtener_stt` qué
`SpeechToText` transcribe las Notas de Voz (Tarea 11.4). Ambos fallan hacia lo
seguro: si el proveedor configurado no puede usarse (sin key, key con formato
inválido o dominio fuera de la allowlist de SSRF), registran el motivo sin datos
sensibles y devuelven el respaldo seguro (respuesta genérica, o "pide repetir"
en la voz). Así un error de configuración nunca deja al Usuario sin respuesta
ni envía datos a un destino no autorizado.
"""

from __future__ import annotations

import logging

from app.chat.gemini import GEMINI_HOST, GeminiModel
from app.chat.gemini_stt import GeminiSpeechToText
from app.chat.inference import GenerativeModel, SafeFallbackModel, SpeechToText, UnavailableStt
from app.common.config import Settings, get_settings
from app.common.logging import log_event

logger = logging.getLogger("cima.chat")


def _dominio_permitido(settings: Settings, host: str) -> bool:
    """Indica si el host está en la allowlist de consumo externo (Req 10.4)."""
    crudo = settings.http_allowlist_domains or ""
    return host in {d.strip().lower() for d in crudo.split(",") if d.strip()}


def _clave_gemini(config: Settings, uso: str) -> str | None:
    """Devuelve la key si Gemini puede usarse; si no, registra el motivo y None.

    `uso` ("llm" o "stt") solo identifica el registro; nunca se registra la key.
    """
    clave = config.gemini_api_key.get_secret_value().strip() if config.gemini_api_key else ""
    if not clave:
        log_event(logger, f"chat_{uso}_sin_credencial", provider="gemini")
        return None
    if not _dominio_permitido(config, GEMINI_HOST):
        log_event(logger, f"chat_{uso}_host_no_permitido", provider="gemini", host=GEMINI_HOST)
        return None
    return clave


def _nivel(nivel: str) -> str | None:
    """Con "none" no se envía el parámetro (modelos que no lo admiten)."""
    return None if nivel == "none" else nivel


def obtener_modelo(settings: Settings | None = None) -> GenerativeModel:
    """Devuelve el modelo configurado o, si no puede usarse, el respaldo seguro.

    Args:
        settings: configuración a usar; por defecto la de la aplicación. Las
            pruebas pasan una propia para no depender de `backend/.env`.
    """
    config = settings or get_settings()
    if config.chat_llm_provider != "gemini":
        return SafeFallbackModel()
    clave = _clave_gemini(config, "llm")
    if clave is None:
        return SafeFallbackModel()
    try:
        return GeminiModel(
            clave,
            config.gemini_model,
            timeout_segundos=config.gemini_timeout_seconds,
            max_output_tokens=config.gemini_max_output_tokens,
            nivel_razonamiento=_nivel(config.gemini_thinking_level),
        )
    except ValueError:
        # El mensaje de GeminiModel no incluye la key; aquí tampoco se registra.
        log_event(logger, "chat_llm_credencial_invalida", provider="gemini")
        return SafeFallbackModel()


def obtener_stt(settings: Settings | None = None) -> SpeechToText:
    """Devuelve el transcriptor configurado o, si no puede usarse, el que pide repetir."""
    config = settings or get_settings()
    if config.chat_stt_provider != "gemini":
        return UnavailableStt()
    clave = _clave_gemini(config, "stt")
    if clave is None:
        return UnavailableStt()
    try:
        return GeminiSpeechToText(
            clave,
            config.gemini_stt_model,
            timeout_segundos=config.gemini_timeout_seconds,
            nivel_razonamiento=_nivel(config.gemini_stt_thinking_level),
        )
    except ValueError:
        log_event(logger, "chat_stt_credencial_invalida", provider="gemini")
        return UnavailableStt()
