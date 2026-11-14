"""Esquemas (DTO) de entrada del Conversational Agent Service.

`ChatTextMessageIn` aplica allowlist de campos (`extra="forbid"`) y tipado
estricto. La regla de longitud (1–2000 caracteres tras trim, Req 3.2) se aplica
en `app.chat.validation` para devolver un error de dominio con el límite
permitido, sin reenviar el contenido del Usuario en la respuesta.
`NotaDeVozValida` es el resultado de validar una Nota de Voz (Req 3.4).
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr

AudioFormat = Literal["m4a", "aac", "ogg", "mp3"]


class ChatTextMessageIn(BaseModel):
    """Mensaje de texto enviado por el Usuario al Agente Conversacional."""

    model_config = ConfigDict(extra="forbid")

    text: StrictStr


class NotaDeVozValida(BaseModel):
    """Nota de Voz que superó la validación y puede pasar a STT (Req 3.3, 3.4)."""

    model_config = ConfigDict(frozen=True)

    formato: AudioFormat
    duracion_segundos: float
    tamano_bytes: int


class ModelResult(BaseModel):
    """Resultado de una invocación al modelo de IA generativa (Tarea 11.3).

    Lo devuelve la implementación de `GenerativeModel`. `model_version` queda en
    el registro auditable (Req 16.4). No contiene PII.
    """

    model_config = ConfigDict(frozen=True)

    text: str
    model_version: str


class TranscriptionResult(BaseModel):
    """Resultado de transcribir una Nota de Voz con STT (Req 14.2, 14.5).

    `confidence` es la confianza del STT en [0, 1]. El texto AÚN PUEDE CONTENER
    PII: la redacción se aplica después, antes del modelo (Req 14.6). No se
    persiste tal cual; solo se usa dentro del pipeline.
    """

    model_config = ConfigDict(frozen=True)

    text: str
    # Zero Trust sobre la respuesta del proveedor: la confianza debe ser un número
    # finito en [0, 1]. Con NaN, `confianza < umbral` da False y la transcripción
    # se habría procesado como confiable (Property 38). Un valor inválido hace
    # fallar la transcripción y el servicio pide repetir (Req 14.5).
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)


class TtsResult(BaseModel):
    """Resultado de sintetizar la respuesta como audio con TTS (Req 14.3).

    `audio_ref` es una referencia a la ubicación del audio generado (no el
    binario), para que el cliente lo reproduzca. No contiene PII.
    """

    model_config = ConfigDict(frozen=True)

    audio_ref: str
    duracion_segundos: float


class TextoRedactado(BaseModel):
    """Texto apto para el modelo de IA, con la PII detectada ya redactada (Req 3.10).

    `categorias` cuenta cuántas sustituciones hubo por tipo de PII (p. ej.
    `{"telefono": 1}`). No contiene los valores originales, por lo que se puede
    usar en el registro auditable sin PII (Req 3.9, 16.4).
    """

    model_config = ConfigDict(frozen=True)

    texto: str
    categorias: dict[str, int]


class ChatMessageAccepted(BaseModel):
    """Acuse de recibo (202) tras encolar la inferencia (Req 3.5, 12.4).

    `processing_after_seconds` indica al cliente a partir de cuántos segundos
    mostrar el indicador de procesamiento (Req 3.7).
    """

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    status: str
    processing_after_seconds: int
    # Solo en Notas de Voz: lo que se entendió, ya redactado de PII, para que el
    # Usuario vea si coincide con lo que dijo (salvaguarda de la transcripción).
    input_redacted: str | None = None


class ChatMessageResult(BaseModel):
    """Estado o resultado de una inferencia encolada (Req 3.6, 3.7, 3.8).

    `response_text` solo viene cuando `status == "listo"`; mientras tanto es
    None. No incluye PII: el contenido ya fue redactado antes de persistir.
    """

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    status: str
    input_channel: str
    response_text: str | None = None
    response_audio_ref: str | None = None


class ChatHistoryItem(BaseModel):
    """Entrada del historial de conversación del Usuario (Req 3.8)."""

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    status: str
    input_channel: str
    input_redacted: str
    response_text: str | None = None


class ChatHistory(BaseModel):
    """Historial de la conversación del Usuario autenticado (Req 3.8)."""

    model_config = ConfigDict(frozen=True)

    items: list[ChatHistoryItem]
