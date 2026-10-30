"""Validación de la entrada del Usuario antes de invocar STT o el modelo de IA.

Funciones puras, sin E/S: se ejecutan antes de cualquier llamada a STT o al
modelo de IA generativa. Si la entrada no cumple, se lanza un error de dominio
y la invocación nunca ocurre (Req 3.2, 3.4). No modifican la entrada original:
el cliente conserva el contenido del Usuario para que lo corrija (Req 3.2).

El formato de audio se determina por los bytes reales de la cabecera, no por la
extensión ni el Content-Type declarados por el cliente (Zero Trust Input).
"""

from __future__ import annotations

import math
import unicodedata

from app.chat.constants import (
    ALLOWED_AUDIO_FORMATS,
    AUDIO_HEADER_MIN_BYTES,
    M4A_BRANDS,
    TEXT_MAX_LENGTH,
    TEXT_MIN_LENGTH,
    VOICE_MAX_BYTES,
    VOICE_MAX_SECONDS,
    VOICE_MIN_SECONDS,
)
from app.chat.dto import AudioFormat, NotaDeVozValida
from app.chat.errors import MensajeInvalidoError, NotaDeVozInvalidaError


def validar_mensaje_texto(texto: str) -> str:
    """Valida y normaliza un mensaje de texto del Usuario (Req 3.1, 3.2).

    Args:
        texto: contenido tal como lo envió el Usuario.

    Returns:
        El texto normalizado (Unicode NFC y sin espacios en los extremos).

    Raises:
        MensajeInvalidoError: si queda vacío tras el trim o supera 2000 caracteres.
    """
    normalizado = unicodedata.normalize("NFC", texto).strip()
    longitud = len(normalizado)
    if longitud < TEXT_MIN_LENGTH:
        raise MensajeInvalidoError(internal_detail="chat_text_empty")
    if longitud > TEXT_MAX_LENGTH:
        raise MensajeInvalidoError(internal_detail=f"chat_text_too_long length={longitud}")
    return normalizado


def detectar_formato_audio(cabecera: bytes) -> AudioFormat | None:
    """Identifica el formato de audio por su firma binaria ("magic bytes").

    Args:
        cabecera: primeros bytes del archivo (se usan al menos 12).

    Returns:
        El formato soportado detectado, o None si no corresponde a ninguno.
    """
    if len(cabecera) < AUDIO_HEADER_MIN_BYTES:
        return None
    if cabecera[:4] == b"OggS":
        return "ogg"
    if cabecera[4:8] == b"ftyp" and cabecera[8:12] in M4A_BRANDS:
        return "m4a"
    if cabecera[:3] == b"ID3":
        return "mp3"
    return _detectar_por_frame_sync(cabecera)


def _detectar_por_frame_sync(cabecera: bytes) -> AudioFormat | None:
    """Distingue AAC (ADTS) de MP3 por los bits de capa tras la sincronía 0xFFF.

    Args:
        cabecera: primeros bytes del archivo.

    Returns:
        "aac" si la capa es 00 (ADTS), "mp3" si es MPEG Layer III, o None.
    """
    if cabecera[0] != 0xFF or (cabecera[1] & 0xE0) != 0xE0:
        return None
    capa = cabecera[1] & 0x06
    if (cabecera[1] & 0xF0) == 0xF0 and capa == 0x00:
        return "aac"
    if capa == 0x02:
        return "mp3"
    return None


def validar_nota_de_voz(audio: bytes, duracion_segundos: float) -> NotaDeVozValida:
    """Valida una Nota de Voz antes de enviarla a STT (Req 3.3, 3.4).

    Args:
        audio: contenido binario completo de la Nota de Voz.
        duracion_segundos: duración medida en el servidor a partir del audio
            (nunca el valor declarado por el cliente).

    Returns:
        La Nota de Voz validada con su formato real, duración y tamaño.

    Raises:
        NotaDeVozInvalidaError: si el tamaño, el formato o la duración no cumplen.
    """
    tamano = len(audio)
    if tamano > VOICE_MAX_BYTES:
        raise NotaDeVozInvalidaError(internal_detail=f"chat_voice_too_large bytes={tamano}")
    formato = detectar_formato_audio(audio[:AUDIO_HEADER_MIN_BYTES])
    if formato is None or formato not in ALLOWED_AUDIO_FORMATS:
        raise NotaDeVozInvalidaError(internal_detail="chat_voice_unsupported_format")
    _validar_duracion(duracion_segundos)
    return NotaDeVozValida(
        formato=formato, duracion_segundos=duracion_segundos, tamano_bytes=tamano
    )


def _validar_duracion(duracion_segundos: float) -> None:
    """Verifica que la duración sea finita y esté entre 1 y 120 s (Req 3.4).

    Args:
        duracion_segundos: duración medida en el servidor.

    Raises:
        NotaDeVozInvalidaError: si la duración no es finita o está fuera de rango.
    """
    if not math.isfinite(duracion_segundos):
        raise NotaDeVozInvalidaError(internal_detail="chat_voice_invalid_duration")
    if not VOICE_MIN_SECONDS <= duracion_segundos <= VOICE_MAX_SECONDS:
        raise NotaDeVozInvalidaError(
            internal_detail=f"chat_voice_duration_out_of_range seconds={duracion_segundos:.1f}"
        )
