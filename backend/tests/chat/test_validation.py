"""Pruebas de la validación de entrada del Conversational Agent Service (Tarea 11.1).

Cubren el rechazo de texto vacío o > 2000 caracteres (Req 3.2) y de Notas de
Voz con formato, duración o tamaño no soportados (Req 3.4), siempre antes de
invocar STT o el modelo de IA. Funciones puras: no hay BD ni servicios externos.
"""
from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from app.chat.constants import TEXT_MAX_LENGTH, VOICE_MAX_BYTES
from app.chat.dto import ChatTextMessageIn
from app.chat.errors import MensajeInvalidoError, NotaDeVozInvalidaError
from app.chat.validation import (
    detectar_formato_audio,
    validar_mensaje_texto,
    validar_nota_de_voz,
)

_RELLENO = b"\x00" * 64

# Cabeceras reales mínimas de cada formato soportado.
OGG = b"OggS\x00\x02" + _RELLENO
M4A = b"\x00\x00\x00\x20ftypM4A " + _RELLENO
MP3_ID3 = b"ID3\x04\x00" + _RELLENO
MP3_FRAME = b"\xff\xfb\x90\x64" + _RELLENO
AAC_ADTS = b"\xff\xf1\x50\x80" + _RELLENO

# Cabeceras de formatos no soportados.
WAV = b"RIFF\x24\x00\x00\x00WAVEfmt " + _RELLENO
FLAC = b"fLaC\x00\x00\x00\x22" + _RELLENO
MP4_VIDEO = b"\x00\x00\x00\x18ftypavc1" + _RELLENO
MPEG_LAYER_I = b"\xff\xff\x90\x64" + _RELLENO


# --- Mensaje de texto (Req 3.1, 3.2) ---------------------------------------


@pytest.mark.parametrize("texto", ["", "   ", "\n\t  \r\n"])
def test_rechaza_texto_vacio_tras_trim(texto: str) -> None:
    """Un mensaje vacío o solo con espacios se rechaza sin llegar al modelo."""
    # Given un texto que queda vacío tras el trim
    # When se valida / Then se rechaza con error de dominio
    with pytest.raises(MensajeInvalidoError):
        validar_mensaje_texto(texto)


def test_rechaza_texto_que_supera_el_limite() -> None:
    """Un mensaje de 2001 caracteres se rechaza (Req 3.2)."""
    # Given un texto que supera en uno el límite
    texto = "a" * (TEXT_MAX_LENGTH + 1)
    # When / Then
    with pytest.raises(MensajeInvalidoError):
        validar_mensaje_texto(texto)


@pytest.mark.parametrize("longitud", [1, TEXT_MAX_LENGTH])
def test_acepta_texto_en_los_limites(longitud: int) -> None:
    """Se aceptan exactamente 1 y 2000 caracteres (extremos incluidos)."""
    # Given un texto con la longitud límite
    texto = "b" * longitud
    # When se valida
    resultado = validar_mensaje_texto(texto)
    # Then se acepta sin cambios
    assert resultado == texto


def test_el_limite_se_cuenta_despues_del_trim() -> None:
    """Los espacios de los extremos no cuentan para el límite de 2000."""
    # Given 2000 caracteres útiles rodeados de espacios
    texto = "  " + "c" * TEXT_MAX_LENGTH + "  "
    # When se valida
    resultado = validar_mensaje_texto(texto)
    # Then se acepta y se devuelve sin los espacios
    assert resultado == "c" * TEXT_MAX_LENGTH


def test_normaliza_unicode_nfc() -> None:
    """Una tilde en forma descompuesta se normaliza a NFC antes de contar."""
    # Given "café" con la tilde como carácter combinante (5 code points)
    texto = "cafe\u0301"
    # When se valida
    resultado = validar_mensaje_texto(texto)
    # Then queda en forma compuesta (4 code points)
    assert resultado == "café"
    assert len(resultado) == 4


def test_no_modifica_el_texto_original() -> None:
    """La validación no altera la entrada: el cliente conserva el contenido (Req 3.2)."""
    # Given un texto con espacios
    original = "  hola, ¿cómo siembro maíz?  "
    copia = str(original)
    # When se valida
    validar_mensaje_texto(original)
    # Then el valor original sigue igual
    assert original == copia


def test_error_de_texto_indica_el_limite_sin_reenviar_el_contenido() -> None:
    """El mensaje público indica el límite y no incluye el texto del Usuario."""
    # Given un texto demasiado largo con un dato sensible
    texto = "mi celular es 3001234567 " * 100
    # When se valida
    with pytest.raises(MensajeInvalidoError) as error:
        validar_mensaje_texto(texto)
    # Then el mensaje público cita el límite y ni el público ni el interno llevan el contenido
    assert str(TEXT_MAX_LENGTH) in error.value.public_message
    assert "3001234567" not in error.value.public_message
    assert "3001234567" not in error.value.internal_detail


def test_dto_rechaza_campos_no_permitidos() -> None:
    """El DTO de texto aplica allowlist de campos (extra='forbid')."""
    # Given un payload con un campo no declarado
    # When se construye el DTO / Then se rechaza
    with pytest.raises(ValidationError):
        ChatTextMessageIn(text="hola", telefono="3001234567")


def test_dto_rechaza_tipos_no_texto() -> None:
    """El campo `text` exige una cadena estricta (sin coerción de números)."""
    with pytest.raises(ValidationError):
        ChatTextMessageIn(text=12345)


# --- Detección del formato real de audio -----------------------------------


@pytest.mark.parametrize(
    ("cabecera", "esperado"),
    [(OGG, "ogg"), (M4A, "m4a"), (MP3_ID3, "mp3"), (MP3_FRAME, "mp3"), (AAC_ADTS, "aac")],
)
def test_detecta_formatos_soportados(cabecera: bytes, esperado: str) -> None:
    """Cada formato soportado se reconoce por su firma binaria."""
    assert detectar_formato_audio(cabecera) == esperado


@pytest.mark.parametrize("cabecera", [WAV, FLAC, MP4_VIDEO, MPEG_LAYER_I, b"", b"OggS"])
def test_no_reconoce_formatos_no_soportados_o_truncados(cabecera: bytes) -> None:
    """WAV, FLAC, video MP4, MPEG Layer I y cabeceras cortas no se aceptan."""
    assert detectar_formato_audio(cabecera) is None


# --- Nota de Voz (Req 3.3, 3.4) --------------------------------------------


@pytest.mark.parametrize("audio", [OGG, M4A, MP3_ID3, AAC_ADTS])
def test_acepta_nota_de_voz_valida(audio: bytes) -> None:
    """Una Nota de Voz soportada y de duración válida pasa a STT."""
    # Given audio soportado de 30 s
    # When se valida
    nota = validar_nota_de_voz(audio, duracion_segundos=30.0)
    # Then queda registrada con su formato real y tamaño
    assert nota.formato == detectar_formato_audio(audio)
    assert nota.tamano_bytes == len(audio)


@pytest.mark.parametrize("duracion", [1.0, 120.0])
def test_acepta_duracion_en_los_limites(duracion: float) -> None:
    """Se aceptan exactamente 1 y 120 segundos (extremos incluidos)."""
    assert validar_nota_de_voz(OGG, duracion_segundos=duracion).duracion_segundos == duracion


@pytest.mark.parametrize("duracion", [0.0, 0.99, 120.01, 600.0, -5.0])
def test_rechaza_duracion_fuera_de_rango(duracion: float) -> None:
    """Duraciones menores a 1 s o mayores a 120 s se rechazan."""
    with pytest.raises(NotaDeVozInvalidaError):
        validar_nota_de_voz(OGG, duracion_segundos=duracion)


@pytest.mark.parametrize("duracion", [math.nan, math.inf, -math.inf])
def test_rechaza_duracion_no_finita(duracion: float) -> None:
    """NaN o infinito no son duraciones válidas."""
    with pytest.raises(NotaDeVozInvalidaError):
        validar_nota_de_voz(OGG, duracion_segundos=duracion)


@pytest.mark.parametrize("audio", [WAV, FLAC, MP4_VIDEO, b"no-es-audio-valido"])
def test_rechaza_formato_no_soportado(audio: bytes) -> None:
    """Un formato fuera de la allowlist se rechaza aunque la duración sea válida."""
    with pytest.raises(NotaDeVozInvalidaError):
        validar_nota_de_voz(audio, duracion_segundos=30.0)


def test_rechaza_nota_de_voz_demasiado_grande() -> None:
    """Un archivo por encima del tamaño máximo se rechaza antes de inspeccionarlo."""
    # Given un ogg válido que excede el tamaño máximo
    audio = OGG + b"\x00" * VOICE_MAX_BYTES
    # When / Then
    with pytest.raises(NotaDeVozInvalidaError):
        validar_nota_de_voz(audio, duracion_segundos=30.0)


def test_error_de_voz_indica_limites_y_formatos() -> None:
    """El mensaje público pide repetir e indica duración y formatos (Req 3.4)."""
    with pytest.raises(NotaDeVozInvalidaError) as error:
        validar_nota_de_voz(WAV, duracion_segundos=30.0)
    mensaje = error.value.public_message
    assert "120" in mensaje
    for formato in ("m4a", "aac", "ogg", "mp3"):
        assert formato in mensaje
