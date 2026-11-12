"""Pruebas de propiedad del Agente Conversacional (Tareas 11.7, 11.8, 11.10, 11.11, 11.12).

- Property 7:  validación de longitud del mensaje de texto (Req 3.2).
- Property 8:  validación de la nota de voz (Req 3.4).
- Property 38: ramificación por confianza de STT (Req 14.5).
- Property 39: guardrails de entrada y validación de salida de IA (Req 16.1, 16.2).
- Property 40: registro auditable de IA sin PII (Req 3.9, 16.4).

Feature: cima-plataforma. Todos los datos son ficticios y generados.
"""
from __future__ import annotations

import math
import string
import unicodedata
import uuid
from unittest.mock import patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.chat import audit, guardrails, service
from app.chat.constants import (
    ESTADO_ENCOLADO,
    ESTADO_REPETIR_VOZ,
    GUARDRAIL_BLOQUEO_ENTRADA,
    GUARDRAIL_PERMITIDO,
    GUARDRAIL_SALIDA_NO_VALIDADA,
    STT_CONFIDENCE_THRESHOLD,
    TEXT_MAX_LENGTH,
    VOICE_MAX_SECONDS,
    VOICE_MIN_SECONDS,
)
from app.chat.dto import ChatTextMessageIn, TranscriptionResult
from app.chat.errors import MensajeInvalidoError, NotaDeVozInvalidaError
from app.chat.models import AiInteraction
from app.chat.validation import validar_mensaje_texto, validar_nota_de_voz
from app.common.resilience import CircuitBreaker
from tests.chat.test_property_9_pii import _celulares, _correos
from tests.chat.test_service import _FakeSession
from tests.chat.test_validation import (
    AAC_ADTS,
    FLAC,
    M4A,
    MP3_FRAME,
    MP3_ID3,
    MP4_VIDEO,
    MPEG_LAYER_I,
    OGG,
    WAV,
)

_ASYNC = settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])


def _variantes(texto: str) -> st.SearchStrategy[str]:
    """Variantes de escritura del mismo texto: mayúsculas, NFD, sin tildes, espacios."""
    sin_tildes = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return st.sampled_from(
        [
            texto,
            texto.upper(),
            texto.title(),
            unicodedata.normalize("NFD", texto),
            sin_tildes,
            texto.replace(" ", "   "),
        ]
    )


def _breaker_aislado() -> CircuitBreaker:
    """Circuit breaker propio de la prueba: las fallas provocadas no abren el compartido."""
    return CircuitBreaker("stt-prueba", failure_threshold=10**6)


# =========================================================================== #
# Property 7 — Validación de longitud del mensaje de texto (Req 3.2)
# =========================================================================== #
_espacios = st.text(alphabet=" \t\n\r", max_size=5)


@st.composite
def _mensajes(draw: st.DrawFn) -> str:
    """Mensajes cerca de los límites (0, 1, 2000, 2001) y textos Unicode cualquiera."""
    if draw(st.booleans()):
        n = draw(
            st.sampled_from([0, 1, 2, TEXT_MAX_LENGTH - 1, TEXT_MAX_LENGTH, TEXT_MAX_LENGTH + 1])
            | st.integers(min_value=0, max_value=TEXT_MAX_LENGTH + 5)
        )
        return draw(_espacios) + "a" * n + draw(_espacios)
    return draw(st.text(max_size=60))


# Feature: cima-plataforma, Property 7: Validación de longitud del mensaje de texto.
# Validates: Requirements 3.2
@settings(max_examples=300, deadline=None)
@given(texto=_mensajes())
def test_property_7_se_acepta_si_y_solo_si_la_longitud_tras_trim_esta_en_rango(texto: str) -> None:
    normalizado = unicodedata.normalize("NFC", texto).strip()
    if 1 <= len(normalizado) <= TEXT_MAX_LENGTH:
        assert validar_mensaje_texto(texto) == normalizado
    else:
        with pytest.raises(MensajeInvalidoError) as error:
            validar_mensaje_texto(texto)
        # El mensaje público no devuelve el contenido: el cliente lo conserva.
        if normalizado:
            assert normalizado[:20] not in error.value.public_message


# Feature: cima-plataforma, Property 7: Validación de longitud del mensaje de texto.
# Validates: Requirements 3.2
@_ASYNC
@given(n=st.sampled_from([0, TEXT_MAX_LENGTH + 1, TEXT_MAX_LENGTH + 50]), relleno=_espacios)
@pytest.mark.asyncio
async def test_property_7_un_mensaje_invalido_no_se_encola(n: int, relleno: str) -> None:
    """Fuera de rango, no se persiste nada: el modelo nunca llega a invocarse."""
    db = _FakeSession()
    with pytest.raises(MensajeInvalidoError):
        await service.encolar_mensaje_texto(db, uuid.uuid4(), ChatTextMessageIn(text=relleno + "a" * n + relleno))
    assert db.rows == []


# =========================================================================== #
# Property 8 — Validación de la nota de voz (Req 3.4)
# =========================================================================== #
_SOPORTADAS = [OGG, M4A, MP3_ID3, MP3_FRAME, AAC_ADTS]
# Cabeceras completas (≥ 12 bytes) de formatos no soportados: se les puede
# agregar cualquier cola sin que cambie el formato detectado.
_NO_SOPORTADAS_COMPLETAS = [WAV, FLAC, MP4_VIDEO, MPEG_LAYER_I, b"%PDF-1.7" + b"\x00" * 64]
# Truncadas: solas no forman una cabecera. Con una cola podrían completarse (p. ej.
# "OggS" + 8 bytes es un OGG válido), así que solo se prueban sin cola.
_TRUNCADAS = [b"", b"OggS"]
_NO_SOPORTADAS = _NO_SOPORTADAS_COMPLETAS + _TRUNCADAS
_duraciones = st.floats(allow_nan=True, allow_infinity=True) | st.floats(min_value=0.0, max_value=130.0)


def _es_valida(cabecera: bytes, duracion: float) -> bool:
    return (
        cabecera in _SOPORTADAS
        and math.isfinite(duracion)
        and VOICE_MIN_SECONDS <= duracion <= VOICE_MAX_SECONDS
    )


# Feature: cima-plataforma, Property 8: Validación de la nota de voz.
# Validates: Requirements 3.4
@settings(max_examples=400, deadline=None)
@given(
    cabecera=st.sampled_from(_SOPORTADAS + _NO_SOPORTADAS_COMPLETAS),
    cola=st.binary(max_size=200),
    duracion=_duraciones,
)
def test_property_8_se_procesa_si_y_solo_si_formato_y_duracion_son_validos(
    cabecera: bytes, cola: bytes, duracion: float
) -> None:
    audio = cabecera + cola
    if _es_valida(cabecera, duracion):
        assert validar_nota_de_voz(audio, duracion).duracion_segundos == duracion
    else:
        with pytest.raises(NotaDeVozInvalidaError):
            validar_nota_de_voz(audio, duracion)


class _SttEspia:
    def __init__(self) -> None:
        self.llamadas = 0

    async def transcribe(self, audio: bytes, audio_format: str) -> TranscriptionResult:
        self.llamadas += 1
        return TranscriptionResult(text="cómo ahorro", confidence=0.9)


# Feature: cima-plataforma, Property 8: Validación de la nota de voz.
# Validates: Requirements 3.4
@_ASYNC
@given(cabecera=st.sampled_from(_SOPORTADAS + _NO_SOPORTADAS), duracion=_duraciones)
@pytest.mark.asyncio
async def test_property_8_una_nota_invalida_no_llega_a_stt(cabecera: bytes, duracion: float) -> None:
    db, stt = _FakeSession(), _SttEspia()
    with patch.object(service, "_stt_breaker", _breaker_aislado()):
        if _es_valida(cabecera, duracion):
            await service.encolar_nota_de_voz(db, uuid.uuid4(), cabecera, duracion, stt=stt)
            assert stt.llamadas == 1
        else:
            with pytest.raises(NotaDeVozInvalidaError):
                await service.encolar_nota_de_voz(db, uuid.uuid4(), cabecera, duracion, stt=stt)
            assert stt.llamadas == 0
            assert db.rows == []


# =========================================================================== #
# Property 38 — Ramificación por confianza de STT (Req 14.5)
# =========================================================================== #
_TRANSCRIPCION = "cómo protejo mi café de la sequía"


class _SttCon:
    """STT simulado que devuelve un texto fijo con la confianza indicada."""

    def __init__(self, confianza: float) -> None:
        self.confianza = confianza

    async def transcribe(self, audio: bytes, audio_format: str) -> TranscriptionResult:
        # Construcción validada, como haría un adaptador real: una confianza
        # inválida (NaN, infinita o fuera de [0, 1]) falla aquí.
        return TranscriptionResult(text=_TRANSCRIPCION, confidence=self.confianza)


async def _estado_por_confianza(confianza: float) -> tuple[str, AiInteraction]:
    db = _FakeSession()
    with patch.object(service, "_stt_breaker", _breaker_aislado()):
        acuse = await service.encolar_nota_de_voz(db, uuid.uuid4(), OGG, 10.0, stt=_SttCon(confianza))
    return acuse.status, db.rows[0]


# Feature: cima-plataforma, Property 38: Ramificación por confianza de STT.
# Validates: Requirements 14.5
@_ASYNC
@given(confianza=st.floats(min_value=0.0, max_value=1.0))
@pytest.mark.asyncio
async def test_property_38_bajo_el_umbral_pide_repetir_y_desde_el_umbral_procesa(confianza: float) -> None:
    estado, fila = await _estado_por_confianza(confianza)
    if confianza < STT_CONFIDENCE_THRESHOLD:
        assert estado == ESTADO_REPETIR_VOZ
        assert fila.input_redacted == ""  # no se conserva la transcripción dudosa
    else:
        assert estado == ESTADO_ENCOLADO
        assert fila.input_redacted == _TRANSCRIPCION


# Feature: cima-plataforma, Property 38: Ramificación por confianza de STT.
# Validates: Requirements 14.5
@_ASYNC
@given(
    confianza=st.sampled_from([math.nan, math.inf, -math.inf])
    | st.floats(max_value=-1e-9, allow_nan=False, allow_infinity=False)
    | st.floats(min_value=1.0 + 1e-9, allow_nan=False, allow_infinity=False)
)
@pytest.mark.asyncio
async def test_property_38_una_confianza_invalida_del_proveedor_pide_repetir(confianza: float) -> None:
    """Regresión: con NaN, `confianza < umbral` daba False y se procesaba como confiable."""
    estado, _ = await _estado_por_confianza(confianza)
    assert estado == ESTADO_REPETIR_VOZ


@pytest.mark.asyncio
async def test_el_umbral_exacto_se_procesa() -> None:
    """Igual o superior al umbral se procesa (Req 14.5): el borde está incluido."""
    estado, _ = await _estado_por_confianza(STT_CONFIDENCE_THRESHOLD)
    assert estado == ESTADO_ENCOLADO


# =========================================================================== #
# Property 39 — Guardrails de entrada y validación de salida (Req 16.1, 16.2)
# =========================================================================== #
_ENTRADAS_BLOQUEADAS = [
    "me garantizas ganancias si invierto",
    "garantiza rentabilidad",
    "invierte todo en eso",
    "¿Es bueno un préstamo gota a gota?",
    "cómo fabricar una bomba",
]
_CONTEXTO = st.sampled_from(["", "hola, ", "una pregunta: ", "oiga "])

_PREGUNTAS_DEL_DOMINIO = [
    "¿cómo ahorro para la próxima cosecha?",
    "¿qué abono uso para el café?",
    "¿cómo protejo mi tienda de una inundación?",
    "quiero aprender a llevar las cuentas del negocio",
    "¿cuándo conviene abonar el cultivo antes de la lluvia?",
    "¿qué es un préstamo formal y cómo lo pido?",
]


# Feature: cima-plataforma, Property 39: Guardrails de entrada y validación de salida.
# Validates: Requirements 16.1
@settings(max_examples=300, deadline=None)
@given(data=st.data(), antes=_CONTEXTO)
def test_property_39_una_entrada_indebida_se_bloquea_como_sea_que_se_escriba(
    data: st.DataObject, antes: str
) -> None:
    """Regresión: con tildes descompuestas (NFD, posible en una transcripción) pasaba."""
    frase = data.draw(st.sampled_from(_ENTRADAS_BLOQUEADAS))
    variante = data.draw(_variantes(frase))
    assert guardrails.evaluar_entrada(antes + variante) == GUARDRAIL_BLOQUEO_ENTRADA


# Feature: cima-plataforma, Property 39: Guardrails de entrada y validación de salida.
# Validates: Requirements 16.1
@settings(max_examples=100, deadline=None)
@given(data=st.data())
def test_property_39_las_preguntas_del_dominio_pasan(data: st.DataObject) -> None:
    pregunta = data.draw(st.sampled_from(_PREGUNTAS_DEL_DOMINIO))
    assert guardrails.evaluar_entrada(data.draw(_variantes(pregunta))) == GUARDRAIL_PERMITIDO


_SALIDAS_CON_INCENTIVO = [
    "Por terminar la ruta te damos un bono de 50.000 pesos.",
    "Recibes una bonificación especial este mes.",
    "Te regalo un seguro para tu cultivo.",
    "Este curso incluye un seguro gratis.",
    "La afiliación es gratuita si te inscribes hoy.",
    "Tienes una rebaja especial si pagas hoy.",
    "Ganaste un premio por completar la cápsula.",
    "Usa este cupón en tu próxima compra.",
    "Hay un descuento del 20% para ti.",
    "Aprovecha la promoción de temporada.",
    "Te damos un incentivo por terminar.",
    "Contrata el microseguro de cosecha hoy.",
]
_SALIDAS_SIN_OFERTA = [
    "Aplica el abono antes de las lluvias para que el café lo aproveche.",
    "Abonar el cultivo cada tres meses ayuda a la cosecha.",
    "Anota tus gastos cada día para saber cuánto ahorras.",
    "Guarda una parte de lo que vendes cada semana.",
]


# Feature: cima-plataforma, Property 39: Guardrails de entrada y validación de salida.
# Validates: Requirements 16.2
@settings(max_examples=300, deadline=None)
@given(data=st.data())
def test_property_39_un_incentivo_sin_respaldo_no_se_presenta(data: st.DataObject) -> None:
    """Regresión: "bono", "gratis", "rebaja" o "premio" pasaban sin validarse."""
    salida = data.draw(_variantes(data.draw(st.sampled_from(_SALIDAS_CON_INCENTIVO))))
    assert guardrails.menciona_oferta(salida)
    assert guardrails.validar_salida(salida, oferta_respaldada=False) == GUARDRAIL_SALIDA_NO_VALIDADA
    assert guardrails.validar_salida(salida, oferta_respaldada=True) == GUARDRAIL_PERMITIDO


# Feature: cima-plataforma, Property 39: Guardrails de entrada y validación de salida.
# Validates: Requirements 16.2
@settings(max_examples=100, deadline=None)
@given(data=st.data())
def test_property_39_una_respuesta_sin_oferta_no_se_confunde_con_una(data: st.DataObject) -> None:
    """"abono" y "abonar" no son "bono": no deben llevar a la respuesta de respaldo."""
    salida = data.draw(_variantes(data.draw(st.sampled_from(_SALIDAS_SIN_OFERTA))))
    assert not guardrails.menciona_oferta(salida)
    assert guardrails.validar_salida(salida, oferta_respaldada=False) == GUARDRAIL_PERMITIDO


@pytest.mark.parametrize("salida", [s for s in _SALIDAS_CON_INCENTIVO if "microseguro" not in s])
def test_un_incentivo_nunca_se_respalda_con_el_catalogo(salida: str) -> None:
    """El catálogo de Microseguros no tiene incentivos: estos nunca se respaldan."""
    permitidos = frozenset({"microseguro de cosecha"})
    assert not guardrails.oferta_respaldada_por_catalogo(salida, permitidos, permitidos)


# =========================================================================== #
# Property 40 — Registro auditable de IA sin PII (Req 3.9, 16.4)
# =========================================================================== #
# Sin espacios ni dígitos: no forma frases como "me llamo X" ni números, así la
# entrada no dispara la redacción y se puede comparar tal cual.
_palabra = st.text(alphabet=string.ascii_letters + "¿?,.", min_size=1, max_size=40)


def _digitos(texto: str) -> str:
    return "".join(c for c in texto if c.isdigit())


# Feature: cima-plataforma, Property 40: Registro auditable de IA sin PII.
# Validates: Requirements 3.9, 16.4
@settings(max_examples=200, deadline=None)
@given(
    entrada=_palabra,
    antes=_palabra,
    dato=st.one_of(_celulares(), _correos()),
    estado=st.sampled_from(["listo", "error"]),
)
def test_property_40_el_registro_tiene_lo_auditable_y_ninguna_pii(
    entrada: str, antes: str, dato: tuple[str, str], estado: str
) -> None:
    """Regresión: la respuesta del modelo se registraba sin redactar."""
    escrito, valor = dato
    perfil = uuid.uuid4()
    inter = AiInteraction(
        id=uuid.uuid4(),
        profile_id=perfil,
        input_redacted=entrada,
        input_channel="texto",
        status=estado,
        # La salida viene del modelo y puede traer PII que el modelo generó.
        response_text=f"{antes} {escrito}",
        model_version="modelo-prueba-v1",
        guardrail_decision=GUARDRAIL_PERMITIDO,
        correlation_id="corr-prueba-1",
    )
    eventos: list[tuple[str, dict]] = []
    with patch.object(audit, "log_event", lambda _l, mensaje, **ctx: eventos.append((mensaje, ctx))):
        audit.registrar_auditoria(inter)

    assert len(eventos) == 1
    mensaje, ctx = eventos[0]
    assert mensaje == "chat_ai_interaction_audit"
    # Lo auditable (Req 16.4).
    assert ctx["input_redacted"] == entrada
    assert ctx["response"]
    assert ctx["model_version"] == "modelo-prueba-v1"
    assert ctx["guardrail_decision"] == GUARDRAIL_PERMITIDO
    assert ctx["status"] == estado
    # Ninguna PII (Req 3.9): ni el titular ni el dato que generó el modelo.
    registro = " ".join(str(v) for v in ctx.values())
    assert str(perfil) not in registro
    assert valor not in registro
    assert valor not in _digitos(registro)
