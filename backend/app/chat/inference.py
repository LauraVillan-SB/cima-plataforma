"""Contrato del modelo de IA generativa para la inferencia del chat.

Define la interfaz que el worker usa para obtener una respuesta del modelo, sin
acoplarse a un proveedor concreto. El modelo recibe un prompt con los mensajes
system/developer/user separados (`app/chat/prompt.py`, Tarea 11.4). Aquí viven
los contratos y respaldos seguros que permiten operar el pipeline de extremo a
extremo sin proveedores externos; los adaptadores reales de LLM y STT/TTS
quedan pendientes de la elección del proveedor.

El worker invoca al modelo a través del circuit breaker de
`app/common/resilience.py` (Req 11.5, 11.6) y le pasa SIEMPRE texto ya redactado
de PII (Tarea 11.2); este módulo no debe recibir PII.
"""

from __future__ import annotations

from typing import Protocol

from app.chat.dto import ModelResult, TranscriptionResult, TtsResult
from app.chat.prompt import PromptConversacional


class GenerativeModel(Protocol):
    """Modelo de IA generativa que responde a un prompt con roles separados.

    Recibe el `PromptConversacional` (system/developer/user) y NO un texto suelto:
    el adaptador del proveedor debe enviar cada rol en su campo propio y nunca
    concatenar las instrucciones con el texto del Usuario (Tarea 11.4, OWASP
    LLM01). `prompt.user` ya viene redactado de PII.
    """

    async def generate(self, prompt: PromptConversacional) -> ModelResult:
        """Genera una respuesta para el prompt (sin PII) y devuelve su versión."""
        ...


class SpeechToText(Protocol):
    """Transcriptor de audio a texto (STT).

    Recibe el binario de la Nota de Voz (ya validada en formato/duración por la
    Tarea 11.1) y devuelve la transcripción con su confianza. El texto resultante
    puede contener PII; el pipeline lo redacta antes del modelo (Req 14.6).
    """

    async def transcribe(self, audio: bytes, audio_format: str) -> TranscriptionResult:
        """Transcribe el audio y devuelve el texto con su confianza [0, 1]."""
        ...


class TextToSpeech(Protocol):
    """Sintetizador de texto a voz (TTS) con voz neutra colombiana (Req 14.3)."""

    async def synthesize(self, text: str) -> TtsResult:
        """Genera el audio de la respuesta y devuelve su referencia y duración."""
        ...


class SafeFallbackModel:
    """Modelo de respaldo seguro: responde de forma genérica sin proveedor externo.

    Se usa como valor por defecto y como fallback del circuit breaker. No inventa
    datos ni ofertas (Req 16.2/16.3): entrega un mensaje en español coloquial que
    pide reformular o esperar. La implementación real del proveedor llega en la
    Tarea 11.4.
    """

    MODEL_VERSION = "fallback-seguro-v1"

    async def generate(self, prompt: PromptConversacional) -> ModelResult:
        """Devuelve una respuesta de respaldo segura e identificable como IA."""
        return ModelResult(
            text=(
                "Soy el asistente de CIMA. Por ahora no puedo darte una respuesta "
                "completa; intenta de nuevo en un momento o reformula tu pregunta."
            ),
            model_version=self.MODEL_VERSION,
        )


class UnavailableStt:
    """STT de respaldo: sin proveedor, devuelve confianza 0 para pedir repetir.

    Permite operar el pipeline sin un proveedor de STT real. Una confianza 0 cae
    por debajo del umbral, de modo que el servicio pedirá al Usuario repetir en
    lenguaje simple (Req 14.5) en lugar de inventar una transcripción.
    """

    async def transcribe(self, audio: bytes, audio_format: str) -> TranscriptionResult:
        """Devuelve una transcripción vacía con confianza 0 (fuerza repetición)."""
        return TranscriptionResult(text="", confidence=0.0)


class NoopTts:
    """TTS de respaldo: no sintetiza audio; el intercambio conserva el texto.

    Devuelve una referencia vacía para indicar que no hay audio disponible. El
    cliente muestra el texto igual (la voz es adicional al texto, Req 14.3).
    """

    async def synthesize(self, text: str) -> TtsResult:
        """Devuelve un resultado sin audio (referencia vacía, duración 0)."""
        return TtsResult(audio_ref="", duracion_segundos=0.0)
