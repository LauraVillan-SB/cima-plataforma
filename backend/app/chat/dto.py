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

from pydantic import BaseModel, ConfigDict, StrictStr

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


class TextoRedactado(BaseModel):
    """Texto apto para el modelo de IA, con la PII detectada ya redactada (Req 3.10).

    `categorias` cuenta cuántas sustituciones hubo por tipo de PII (p. ej.
    `{"telefono": 1}`). No contiene los valores originales, por lo que se puede
    usar en el registro auditable sin PII (Req 3.9, 16.4).
    """

    model_config = ConfigDict(frozen=True)

    texto: str
    categorias: dict[str, int]


class ChatMessageEnqueueIn(BaseModel):
    """Entrada para encolar un mensaje de texto para inferencia (Tarea 11.3).

    `client_event_id` da idempotencia al envío (reintentos no duplican). No
    incluye `profile_id`: el titular se resuelve desde la cookie de sesión
    (anti-BOLA). El texto se valida y redacta en el servidor antes de encolar.
    """

    model_config = ConfigDict(extra="forbid")

    client_event_id: uuid.UUID
    text: StrictStr


class ChatMessageStatusOut(BaseModel):
    """Estado de un mensaje de chat y su respuesta cuando está lista (Req 3.5–3.8).

    No expone PII: `redacted_input` es la entrada ya redactada. `show_indicator`
    le dice al cliente si debe mostrar el indicador de procesamiento (Req 3.7).
    """

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    status: str
    source: str
    redacted_input: str
    response: str | None
    show_indicator: bool


class ChatHistoryItem(BaseModel):
    """Elemento del historial de conversación del Usuario (Req 3.8); sin PII."""

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    status: str
    source: str
    redacted_input: str
    response: str | None


class ChatHistory(BaseModel):
    """Historial de conversación del Usuario autenticado, más reciente primero."""

    model_config = ConfigDict(frozen=True)

    items: list[ChatHistoryItem]
