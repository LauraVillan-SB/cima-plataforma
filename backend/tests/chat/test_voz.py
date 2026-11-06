"""Pruebas del pipeline de voz del chat (Tarea 11.4).

Cubren la transcripción STT y la ramificación por confianza (Req 14.5), la
redacción de PII de la transcripción antes de encolar (Req 14.6), que el audio
no se persista, y la síntesis TTS de la respuesta en el worker (Req 14.3).

No usan BD real: una sesión en memoria simula `get`, `add`, `commit` y
`refresh`. STT y TTS se inyectan como dobles de prueba. Audio y datos ficticios.
"""
from __future__ import annotations

import uuid

import pytest

from app.chat import service
from app.chat.constants import (
    CANAL_VOZ,
    ESTADO_ENCOLADO,
    ESTADO_LISTO,
    ESTADO_REPETIR_VOZ,
)
from app.chat.dto import ModelResult, TranscriptionResult, TtsResult
from app.chat.errors import NotaDeVozInvalidaError
from app.chat.models import AiInteraction

# Cabecera OGG válida mínima (reutiliza el formato aceptado por la Tarea 11.1).
OGG = b"OggS\x00\x02" + b"\x00" * 64


class _FakeSession:
    def __init__(self) -> None:
        self.rows: list[AiInteraction] = []

    def add(self, obj: object) -> None:
        if isinstance(obj, AiInteraction):
            if obj.id is None:
                obj.id = uuid.uuid4()
            if obj not in self.rows:
                self.rows.append(obj)

    async def commit(self) -> None:
        return None

    async def refresh(self, obj: object) -> None:
        return None

    async def get(self, _model, pk):  # noqa: ANN001 - stub
        return next((r for r in self.rows if r.id == pk), None)


class _Stt:
    """STT de prueba con texto y confianza configurables."""

    def __init__(self, text: str, confidence: float) -> None:
        self._text = text
        self._confidence = confidence

    async def transcribe(self, audio: bytes, audio_format: str) -> TranscriptionResult:
        return TranscriptionResult(text=self._text, confidence=self._confidence)


class _SttFalla:
    async def transcribe(self, audio: bytes, audio_format: str) -> TranscriptionResult:
        raise RuntimeError("STT no disponible")


class _ModeloOk:
    async def generate(self, redacted_text: str) -> ModelResult:
        return ModelResult(text="respuesta", model_version="test-v1")


class _Tts:
    async def synthesize(self, text: str) -> TtsResult:
        return TtsResult(audio_ref="audio://resp-1", duracion_segundos=4.0)


class _TtsFalla:
    async def synthesize(self, text: str) -> TtsResult:
        raise RuntimeError("TTS no disponible")


# --- Encolado de voz y confianza (Req 14.2, 14.5) --------------------------


@pytest.mark.asyncio
async def test_voz_confiable_se_encola_y_redacta() -> None:
    """Una transcripción confiable se redacta y queda encolada (Req 14.6)."""
    # Given un STT que transcribe con confianza alta e incluye un celular
    db = _FakeSession()
    usuario = uuid.uuid4()
    stt = _Stt(text="mi celular es 3001234567 y siembro cafe", confidence=0.9)
    # When se encola la nota de voz
    acuse = await service.encolar_nota_de_voz(db, usuario, OGG, 10.0, stt=stt)
    # Then queda encolada, por el canal voz, con la PII ya redactada
    assert acuse.status == ESTADO_ENCOLADO
    guardada = db.rows[0]
    assert guardada.input_channel == CANAL_VOZ
    assert "3001234567" not in guardada.input_redacted
    assert "[TELEFONO]" in guardada.input_redacted


@pytest.mark.asyncio
async def test_voz_baja_confianza_pide_repetir() -> None:
    """Confianza por debajo del umbral no invoca el modelo y pide repetir (Req 14.5)."""
    db = _FakeSession()
    stt = _Stt(text="algo ininteligible", confidence=0.3)
    acuse = await service.encolar_nota_de_voz(db, uuid.uuid4(), OGG, 10.0, stt=stt)
    assert acuse.status == ESTADO_REPETIR_VOZ
    # No se persiste contenido del Usuario cuando se pide repetir.
    assert db.rows[0].input_redacted == ""


@pytest.mark.asyncio
async def test_voz_transcripcion_vacia_pide_repetir() -> None:
    """Una transcripción vacía (aunque la confianza sea alta) pide repetir."""
    db = _FakeSession()
    stt = _Stt(text="   ", confidence=0.95)
    acuse = await service.encolar_nota_de_voz(db, uuid.uuid4(), OGG, 10.0, stt=stt)
    assert acuse.status == ESTADO_REPETIR_VOZ


@pytest.mark.asyncio
async def test_voz_stt_falla_pide_repetir_sin_culpar() -> None:
    """Si el STT falla, se pide repetir sin invocar el modelo (Req 14.5)."""
    db = _FakeSession()
    acuse = await service.encolar_nota_de_voz(db, uuid.uuid4(), OGG, 10.0, stt=_SttFalla())
    assert acuse.status == ESTADO_REPETIR_VOZ


@pytest.mark.asyncio
async def test_voz_audio_invalido_se_rechaza_sin_stt() -> None:
    """Un audio con formato no soportado se rechaza antes de transcribir (Req 3.4)."""
    db = _FakeSession()
    stt = _Stt(text="no deberia llamarse", confidence=0.9)
    with pytest.raises(NotaDeVozInvalidaError):
        await service.encolar_nota_de_voz(db, uuid.uuid4(), b"no-es-audio", 10.0, stt=stt)
    assert db.rows == []


@pytest.mark.asyncio
async def test_voz_duracion_fuera_de_rango_se_rechaza() -> None:
    """Una duración fuera de [1, 120] s se rechaza antes de transcribir (Req 3.4)."""
    db = _FakeSession()
    stt = _Stt(text="hola", confidence=0.9)
    with pytest.raises(NotaDeVozInvalidaError):
        await service.encolar_nota_de_voz(db, uuid.uuid4(), OGG, 200.0, stt=stt)


# --- Síntesis TTS en el worker (Req 14.3) ----------------------------------


@pytest.mark.asyncio
async def test_worker_sintetiza_audio_de_la_respuesta() -> None:
    """La inferencia exitosa guarda la referencia del audio TTS (Req 14.3)."""
    db = _FakeSession()
    inter = AiInteraction(
        id=uuid.uuid4(), profile_id=uuid.uuid4(), input_redacted="hola",
        input_channel=CANAL_VOZ, status=ESTADO_ENCOLADO, response_text=None,
        response_audio_ref=None, model_version=None, correlation_id=None, created_at=0,
    )
    db.rows.append(inter)
    await service.procesar_inferencia(db, inter.id, modelo=_ModeloOk(), tts=_Tts())
    assert inter.status == ESTADO_LISTO
    # La respuesta lleva la marca de IA (Req 16.5), por eso se verifica con "in".
    assert "respuesta" in inter.response_text
    assert inter.response_audio_ref == "audio://resp-1"


@pytest.mark.asyncio
async def test_worker_sin_tts_conserva_texto() -> None:
    """Si el TTS falla, la respuesta de texto se conserva y el audio queda nulo."""
    db = _FakeSession()
    inter = AiInteraction(
        id=uuid.uuid4(), profile_id=uuid.uuid4(), input_redacted="hola",
        input_channel=CANAL_VOZ, status=ESTADO_ENCOLADO, response_text=None,
        response_audio_ref=None, model_version=None, correlation_id=None, created_at=0,
    )
    db.rows.append(inter)
    await service.procesar_inferencia(db, inter.id, modelo=_ModeloOk(), tts=_TtsFalla())
    assert inter.status == ESTADO_LISTO
    # La respuesta lleva la marca de IA (Req 16.5), por eso se verifica con "in".
    assert "respuesta" in inter.response_text
    assert inter.response_audio_ref is None
