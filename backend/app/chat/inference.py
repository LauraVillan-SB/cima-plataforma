"""Contrato del modelo de IA generativa para la inferencia del chat.

Define la interfaz que el worker usa para obtener una respuesta del modelo, sin
acoplarse a un proveedor concreto. La implementación real (prompts
system/developer/user separados, STT/TTS, guardrails) corresponde a la Tarea
11.4/11.5; aquí solo vive el contrato y una implementación de respaldo segura
que permite operar el pipeline de extremo a extremo sin un proveedor externo.

El worker invoca al modelo a través del circuit breaker de
`app/common/resilience.py` (Req 11.5, 11.6) y le pasa SIEMPRE texto ya redactado
de PII (Tarea 11.2); este módulo no debe recibir PII.
"""

from __future__ import annotations

from typing import Protocol

from app.chat.dto import ModelResult


class GenerativeModel(Protocol):
    """Modelo de IA generativa capaz de responder a un texto ya redactado."""

    async def generate(self, redacted_text: str) -> ModelResult:
        """Genera una respuesta para el texto (sin PII) y devuelve su versión."""
        ...


class SafeFallbackModel:
    """Modelo de respaldo seguro: responde de forma genérica sin proveedor externo.

    Se usa como valor por defecto y como fallback del circuit breaker. No inventa
    datos ni ofertas (Req 16.2/16.3): entrega un mensaje en español coloquial que
    pide reformular o esperar. La implementación real del proveedor llega en la
    Tarea 11.4.
    """

    MODEL_VERSION = "fallback-seguro-v1"

    async def generate(self, redacted_text: str) -> ModelResult:
        """Devuelve una respuesta de respaldo segura e identificable como IA."""
        return ModelResult(
            text=(
                "Soy el asistente de CIMA. Por ahora no puedo darte una respuesta "
                "completa; intenta de nuevo en un momento o reformula tu pregunta."
            ),
            model_version=self.MODEL_VERSION,
        )
