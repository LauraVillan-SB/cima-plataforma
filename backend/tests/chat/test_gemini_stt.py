"""Pruebas de la transcripción de Notas de Voz con Gemini (Tarea 11.4).

Sin red: Gemini se simula con `httpx.MockTransport` y la resolución DNS se fija
a una IP pública. Audio de prueba: solo cabeceras válidas, sin voz real.

Cubren:
- La petición: instrucción fija en `systemInstruction`, audio solo como
  `inlineData` con el MIME estándar del formato, salida estructurada pedida
  ("describir primero": la descripción va antes que la transcripción) y key
  solo en la cabecera, sin redirecciones.
- Salvaguardas (Gemini no da confianza y puede inventar frases con silencio):
  sin voz, no se entiende, texto vacío o marcador de inaudible → confianza 0;
  solo "hay voz, se entiende y hay texto" llega a `CONFIANZA_ENTENDIDA`.
- Zero Trust: salida no JSON, con tipos o campos inesperados, faltantes,
  demasiado larga o respuesta cortada → `ProveedorIaError`.
- Selección por configuración (`obtener_stt`) con caída al respaldo.
- Flujo completo: lo entendido se redacta, se encola y vuelve en el acuse; lo
  no entendido pide repetir sin guardar contenido.

Validates: Requirements 3.10, 10.4, 14.2, 14.5, 14.6
"""

from __future__ import annotations

import base64
import json
import logging
import uuid
from unittest.mock import patch

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.chat import service
from app.chat.constants import (
    ESTADO_ENCOLADO,
    ESTADO_REPETIR_VOZ,
    STT_CONFIDENCE_THRESHOLD,
    TEXT_MAX_LENGTH,
)
from app.chat.gemini import GEMINI_HOST, ProveedorIaError
from app.chat.gemini_stt import (
    CONFIANZA_ENTENDIDA,
    INSTRUCCION_TRANSCRIPCION,
    MIME_POR_FORMATO,
    GeminiSpeechToText,
)
from app.chat.inference import UnavailableStt
from app.chat.proveedores import obtener_stt
from app.common import http_client
from app.common.config import Settings
from app.common.http_client import SsrfBlockedError
from app.common.resilience import CircuitBreaker
from tests.chat.test_voz import OGG, _FakeSession

# Valores ficticios: no son secretos ni datos reales.
_KEY = "clave-ficticia-de-prueba_0123456789ABCDEF"
_MODELO = "gemini-de-prueba-1.0"
_URL = f"https://{GEMINI_HOST}/v1beta/models/{_MODELO}:generateContent"
_IP_PUBLICA = [("", "", "", "", ("142.250.0.10", 0))]
_ALLOWLIST = f"sostenibilidadbolivar.com,{GEMINI_HOST}"
_CAMPOS = ["lo_que_se_escucha", "hay_voz", "se_entiende", "texto"]


def _salida(hay_voz: bool, se_entiende: bool, texto: str, escucha: str = "voz de una persona") -> dict:
    """Salida estructurada como la devuelve Gemini."""
    return {"lo_que_se_escucha": escucha, "hay_voz": hay_voz, "se_entiende": se_entiende, "texto": texto}


def _respuesta(salida: object, fin: str = "STOP") -> httpx.Response:
    """Respuesta de Gemini cuyo texto es `salida` (dict → JSON, str tal cual)."""
    texto = salida if isinstance(salida, str) else json.dumps(salida, ensure_ascii=False)
    return httpx.Response(
        200,
        json={
            "candidates": [{"content": {"role": "model", "parts": [{"text": texto}]}, "finishReason": fin}],
            "modelVersion": _MODELO,
        },
    )


def _stt(
    recibidas: list[httpx.Request], respuesta: httpx.Response, nivel: str | None = "low"
) -> GeminiSpeechToText:
    def manejar(request: httpx.Request) -> httpx.Response:
        recibidas.append(request)
        return respuesta

    return GeminiSpeechToText(
        _KEY, _MODELO, timeout_segundos=5.0, nivel_razonamiento=nivel, transport=httpx.MockTransport(manejar)
    )


@pytest.fixture(autouse=True)
def _red_simulada():
    """Gemini en la allowlist y DNS fijo a una IP pública, sin red real."""
    with patch.dict("os.environ", {"HTTP_ALLOWLIST_DOMAINS": _ALLOWLIST}):
        http_client.get_settings.cache_clear()
        with patch.object(http_client.socket, "getaddrinfo", return_value=_IP_PUBLICA):
            yield
    http_client.get_settings.cache_clear()


# --------------------------------------------------------------------------- #
# Petición
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
@pytest.mark.parametrize("formato", sorted(MIME_POR_FORMATO))
async def test_la_peticion_lleva_el_audio_con_su_mime_y_la_instruccion_fija(formato: str) -> None:
    recibidas: list[httpx.Request] = []
    stt = _stt(recibidas, _respuesta(_salida(True, True, "hola")))

    await stt.transcribe(b"audio-de-prueba", formato)  # type: ignore[arg-type]

    peticion = recibidas[0]
    assert str(peticion.url) == _URL
    assert peticion.headers["x-goog-api-key"] == _KEY
    assert _KEY not in str(peticion.url)
    cuerpo = json.loads(peticion.content)
    assert cuerpo["systemInstruction"] == {"parts": [{"text": INSTRUCCION_TRANSCRIPCION}]}
    partes = cuerpo["contents"][0]["parts"]
    assert partes == [
        {"inlineData": {"mimeType": MIME_POR_FORMATO[formato], "data": base64.b64encode(b"audio-de-prueba").decode()}}
    ]
    configuracion = cuerpo["generationConfig"]
    assert configuracion["responseMimeType"] == "application/json"
    assert configuracion["temperature"] == 0
    assert configuracion["thinkingConfig"] == {"thinkingLevel": "low"}


def test_el_esquema_pide_describir_lo_que_se_escucha_antes_de_transcribir() -> None:
    """El orden es la salvaguarda contra el silencio: descripción primero, texto al final."""
    esquema = _stt([], httpx.Response(200)).cuerpo(b"audio", "ogg")["generationConfig"]["responseSchema"]

    assert esquema["required"] == _CAMPOS
    assert esquema["propertyOrdering"] == _CAMPOS
    assert set(esquema["properties"]) == set(_CAMPOS)


def test_sin_nivel_de_razonamiento_no_se_envia_el_parametro() -> None:
    configuracion = _stt([], httpx.Response(200), nivel=None).cuerpo(b"audio", "ogg")["generationConfig"]

    assert "thinkingConfig" not in configuracion


@pytest.mark.asyncio
async def test_no_sigue_redirecciones_para_no_reenviar_la_key() -> None:
    recibidas: list[httpx.Request] = []
    stt = _stt(recibidas, httpx.Response(302, headers={"Location": "https://sostenibilidadbolivar.com/x"}))

    with pytest.raises(ProveedorIaError, match="gemini_http_302"):
        await stt.transcribe(b"audio", "ogg")

    assert len(recibidas) == 1


@pytest.mark.asyncio
async def test_fuera_de_la_allowlist_no_se_envia_el_audio() -> None:
    recibidas: list[httpx.Request] = []
    stt = _stt(recibidas, _respuesta(_salida(True, True, "hola")))

    with patch.dict("os.environ", {"HTTP_ALLOWLIST_DOMAINS": "sostenibilidadbolivar.com"}):
        http_client.get_settings.cache_clear()
        with pytest.raises(SsrfBlockedError):
            await stt.transcribe(b"audio", "ogg")
    http_client.get_settings.cache_clear()

    assert recibidas == []


def test_un_formato_fuera_de_la_lista_no_se_envia() -> None:
    with pytest.raises(ProveedorIaError, match="gemini_stt_formato_no_soportado"):
        _stt([], httpx.Response(200)).cuerpo(b"audio", "wav")  # type: ignore[arg-type]


def test_la_key_no_aparece_en_repr_ni_en_errores_de_construccion() -> None:
    assert _KEY not in repr(_stt([], httpx.Response(200)))
    with pytest.raises(ValueError) as error:
        GeminiSpeechToText("key con espacios invalida 0123456789", _MODELO, timeout_segundos=5.0)
    assert "key con espacios" not in str(error.value)


# --------------------------------------------------------------------------- #
# Salvaguardas de la confianza
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_voz_entendida_da_la_confianza_que_supera_el_umbral() -> None:
    stt = _stt([], _respuesta(_salida(True, True, "  ¿Cómo ahorro para la cosecha?  ")))

    resultado = await stt.transcribe(b"audio", "m4a")

    assert resultado.text == "¿Cómo ahorro para la cosecha?"
    assert resultado.confidence == CONFIANZA_ENTENDIDA
    assert resultado.confidence >= STT_CONFIDENCE_THRESHOLD


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "salida",
    [
        _salida(False, False, "", escucha="silencio"),
        # Lo visto con silencio: dice que no hay voz pero igual trae una frase.
        _salida(False, True, "¿Quién te dijo que no?", escucha="silencio"),
        _salida(False, False, "", escucha="ruido"),
        _salida(True, False, "algo que no se entiende"),
        _salida(True, True, "   "),
        _salida(True, True, "[inaudible]"),
        _salida(True, True, "(ruido)"),
        _salida(True, True, "Silencio."),
        _salida(True, True, "*música*"),
        # Lo visto con silencio en lite: una sola letra.
        _salida(True, True, "Y"),
        _salida(True, True, "¿Y?"),
    ],
)
async def test_cualquier_duda_da_confianza_cero_y_texto_vacio(salida: dict) -> None:
    stt = _stt([], _respuesta(salida))

    resultado = await stt.transcribe(b"audio", "ogg")

    assert resultado.confidence == 0.0
    assert resultado.text == ""


@pytest.mark.parametrize("texto", ["Sí", "no", "10"])
def test_las_respuestas_cortas_reales_si_se_procesan(texto: str) -> None:
    resultado = _stt([], httpx.Response(200))._interpretar(_respuesta(_salida(True, True, texto)))

    assert resultado.text == texto
    assert resultado.confidence == CONFIANZA_ENTENDIDA


# Feature: cima-plataforma, Property 38: Ramificación por confianza de STT.
@settings(max_examples=200, deadline=None)
@given(
    hay_voz=st.booleans(),
    se_entiende=st.booleans(),
    texto=st.text(max_size=80),
    escucha=st.text(max_size=40),
)
def test_solo_se_procesa_si_hay_voz_se_entiende_y_hay_texto(
    hay_voz: bool, se_entiende: bool, texto: str, escucha: str
) -> None:
    """Para cualquier salida del modelo, nunca queda sobre el umbral si hay una duda."""
    stt = _stt([], httpx.Response(200))
    resultado = stt._interpretar(_respuesta(_salida(hay_voz, se_entiende, texto, escucha)))

    if resultado.confidence >= STT_CONFIDENCE_THRESHOLD:
        assert hay_voz and se_entiende
        assert sum(1 for c in resultado.text if c.isalnum()) >= 2
    else:
        assert resultado.text == ""


@pytest.mark.parametrize(
    "salida",
    [
        "esto no es json",
        "[]",
        json.dumps({**_salida(True, True, "hola"), "hay_voz": "si"}),  # tipo inesperado
        json.dumps({"lo_que_se_escucha": "voz", "hay_voz": True, "se_entiende": True}),  # falta texto
        json.dumps({"hay_voz": True, "se_entiende": True, "texto": "hola"}),  # falta la descripción
        json.dumps({**_salida(True, True, "hola"), "confianza": 1}),  # campo extra
        json.dumps(_salida(True, True, "x" * (TEXT_MAX_LENGTH + 1))),
        json.dumps(_salida(True, True, "hola", escucha="x" * 201)),
    ],
)
def test_una_salida_estructurada_invalida_lanza_error(salida: str) -> None:
    with pytest.raises(ProveedorIaError, match="gemini_stt_salida_invalida"):
        _stt([], httpx.Response(200))._interpretar(_respuesta(salida))


def test_una_respuesta_cortada_lanza_error() -> None:
    with pytest.raises(ProveedorIaError, match="gemini_fin_max_tokens"):
        _stt([], httpx.Response(200))._interpretar(_respuesta(_salida(True, True, "hola"), fin="MAX_TOKENS"))


# --------------------------------------------------------------------------- #
# Configuración
# --------------------------------------------------------------------------- #
def _settings(**kw: object) -> Settings:
    base: dict = {"http_allowlist_domains": _ALLOWLIST}
    base.update(kw)
    return Settings(_env_file=None, **base)


def test_por_defecto_la_voz_usa_el_respaldo() -> None:
    assert isinstance(obtener_stt(_settings()), UnavailableStt)


def test_gemini_bien_configurado_usa_el_modelo_probado_sin_razonamiento() -> None:
    """Por defecto: el modelo que no inventó texto con silencio, tal como se probó."""
    stt = obtener_stt(_settings(chat_stt_provider="gemini", gemini_api_key=_KEY))

    assert isinstance(stt, GeminiSpeechToText)
    assert "gemini-3.5-flash-lite" in repr(stt)
    assert "thinkingConfig" not in stt.cuerpo(b"audio", "ogg")["generationConfig"]


def test_el_razonamiento_del_stt_es_independiente_del_modelo_de_texto() -> None:
    stt = obtener_stt(
        _settings(chat_stt_provider="gemini", gemini_api_key=_KEY, gemini_thinking_level="high",
                  gemini_stt_thinking_level="low")
    )

    assert isinstance(stt, GeminiSpeechToText)
    assert stt.cuerpo(b"audio", "ogg")["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}


@pytest.mark.parametrize(
    ("ajustes", "evento"),
    [
        ({}, "chat_stt_sin_credencial"),
        ({"gemini_api_key": _KEY, "http_allowlist_domains": "sostenibilidadbolivar.com"}, "chat_stt_host_no_permitido"),
        ({"gemini_api_key": "key con espacios invalida 0123456789"}, "chat_stt_credencial_invalida"),
    ],
)
def test_gemini_mal_configurado_cae_al_respaldo(ajustes: dict, evento: str, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        stt = obtener_stt(_settings(chat_stt_provider="gemini", **ajustes))

    assert isinstance(stt, UnavailableStt)
    assert evento in caplog.text
    assert _KEY not in caplog.text


# --------------------------------------------------------------------------- #
# Flujo completo de la Nota de Voz
# --------------------------------------------------------------------------- #
def _breaker_aislado() -> CircuitBreaker:
    return CircuitBreaker("stt-prueba", failure_threshold=10**6)


@pytest.mark.asyncio
async def test_lo_entendido_se_redacta_se_encola_y_vuelve_en_el_acuse() -> None:
    db = _FakeSession()
    stt = _stt([], _respuesta(_salida(True, True, "mi celular es 3001234567, ¿cómo ahorro?")))

    with patch.object(service, "_stt_breaker", _breaker_aislado()):
        acuse = await service.encolar_nota_de_voz(db, uuid.uuid4(), OGG, 10.0, stt=stt)

    assert acuse.status == ESTADO_ENCOLADO
    assert acuse.input_redacted == db.rows[0].input_redacted
    assert "3001234567" not in acuse.input_redacted
    assert "[TELEFONO]" in acuse.input_redacted


@pytest.mark.asyncio
async def test_el_silencio_pide_repetir_sin_guardar_contenido() -> None:
    db = _FakeSession()
    stt = _stt([], _respuesta(_salida(False, True, "¿Por qué?", escucha="silencio")))

    with patch.object(service, "_stt_breaker", _breaker_aislado()):
        acuse = await service.encolar_nota_de_voz(db, uuid.uuid4(), OGG, 10.0, stt=stt)

    assert acuse.status == ESTADO_REPETIR_VOZ
    assert acuse.input_redacted is None
    assert db.rows[0].input_redacted == ""


@pytest.mark.asyncio
async def test_si_gemini_falla_se_pide_repetir() -> None:
    db = _FakeSession()
    stt = _stt([], httpx.Response(503, text="no disponible"))

    with patch.object(service, "_stt_breaker", _breaker_aislado()):
        acuse = await service.encolar_nota_de_voz(db, uuid.uuid4(), OGG, 10.0, stt=stt)

    assert acuse.status == ESTADO_REPETIR_VOZ


@pytest.mark.asyncio
async def test_sin_stt_explicito_la_suite_usa_el_respaldo() -> None:
    """La suite fuerza CHAT_STT_PROVIDER=respaldo: nunca transcribe con Gemini real."""
    db = _FakeSession()

    with patch.object(service, "_stt_breaker", _breaker_aislado()):
        acuse = await service.encolar_nota_de_voz(db, uuid.uuid4(), OGG, 10.0)

    assert acuse.status == ESTADO_REPETIR_VOZ
