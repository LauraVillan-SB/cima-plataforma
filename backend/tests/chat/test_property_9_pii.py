"""Prueba de propiedad: no fuga de PII hacia el modelo (Tarea 11.9).

Feature: cima-plataforma, Property 9: No fuga de PII hacia el modelo.
Validates: Requirements 3.10, 3.11, 14.6

*Para todo* mensaje con un dato personal (celular, cédula o correo) escrito como
lo escribiría un Usuario —con o sin separadores, con espacios de más, seguido de
"mil gracias"— la redacción lo reemplaza o rechaza el mensaje; y en el flujo
completo (encolar → worker) el modelo nunca recibe el dato. Si la redacción
falla, el modelo no se invoca y no se persiste nada.

Además, los montos de dinero se conservan: son necesarios para la educación
financiera y no son PII.

Todos los datos son ficticios y generados.
"""
from __future__ import annotations

import uuid

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.chat import service
from app.chat.dto import ChatTextMessageIn, ModelResult
from app.chat.errors import RedaccionPiiError
from app.chat.redaction import MIN_DIGITOS_IDENTIFICADOR, redactar_pii
from tests.chat.test_service import _FakeSession

# Separadores que un Usuario usa entre grupos de dígitos (al escribir o al dictar).
_SEPARADORES = ["", " ", "-", ".", "  ", " - ", " . ", "   ", "/", "_"]

# Contexto sin dígitos alrededor del dato, para que cualquier dígito que quede en
# la salida provenga del dato personal.
_ANTES = st.sampled_from(
    ["", "mi celular es ", "llámame al ", "mi número: ", "hola, soy de la vereda, mi cel ", "cédula "]
)
_DESPUES = st.sampled_from(
    ["", " gracias", " mil gracias", ", mil gracias", " por favor", ". ¿me ayudas con el crédito?"]
)


def _digitos(texto: str) -> str:
    return "".join(c for c in texto if c.isdigit())


@st.composite
def _celulares(draw: st.DrawFn) -> tuple[str, str]:
    """Celular colombiano ficticio (3 + 9 dígitos) en un formato realista."""
    resto = draw(st.text(alphabet="0123456789", min_size=9, max_size=9))
    numero = "3" + resto
    sep = draw(st.sampled_from(_SEPARADORES))
    grupos = draw(
        st.sampled_from([[numero], [numero[:3], numero[3:]], [numero[:3], numero[3:6], numero[6:]]])
    )
    escrito = sep.join(grupos)
    indicativo = draw(st.sampled_from(["", "+57 ", "57 ", "+57"]))
    return indicativo + escrito, numero


@st.composite
def _cedulas(draw: st.DrawFn) -> tuple[str, str]:
    """Cédula ficticia de 6 a 10 dígitos, con o sin puntos de miles o un espacio.

    Limitación conocida: una cédula partida con doble espacio ("100  000") no se
    distingue de dos cantidades sueltas ("100  200 vacas"), así que no se redacta.
    Los celulares sí se cubren con espacios de más porque tienen estructura 3-3-4.
    """
    numero = draw(st.from_regex(r"[1-9][0-9]{5,9}", fullmatch=True))
    sep = draw(st.sampled_from(["", ".", " "]))
    if not sep:
        return numero, numero
    grupos: list[str] = []
    resto = numero
    while len(resto) > 3:
        grupos.insert(0, resto[-3:])
        resto = resto[:-3]
    grupos.insert(0, resto)
    return sep.join(grupos), numero


@st.composite
def _correos(draw: st.DrawFn) -> tuple[str, str]:
    usuario = draw(st.from_regex(r"[a-z][a-z0-9._]{1,10}[a-z0-9]", fullmatch=True))
    dominio = draw(st.sampled_from(["ejemplo.com", "correo.co", "mail.example.org"]))
    correo = f"{usuario}@{dominio}"
    return correo, correo


def _mensaje(antes: str, escrito: str, despues: str) -> str:
    return f"{antes}{escrito}{despues}".strip() or escrito


# --------------------------------------------------------------------------- #
# Nivel de función: la redacción no deja el dato en el texto
# --------------------------------------------------------------------------- #
# Feature: cima-plataforma, Property 9: No fuga de PII hacia el modelo.
# Validates: Requirements 3.10, 3.11
@settings(max_examples=300, deadline=None)
@given(dato=st.one_of(_celulares(), _cedulas()), antes=_ANTES, despues=_DESPUES)
def test_property_9_numero_personal_no_sobrevive_a_la_redaccion(
    dato: tuple[str, str], antes: str, despues: str
) -> None:
    escrito, numero = dato
    texto = _mensaje(antes, escrito, despues)
    try:
        redactado = redactar_pii(texto).texto
    except RedaccionPiiError:
        return  # rechazar también cumple: no llega al modelo
    restantes = _digitos(redactado)
    assert numero not in restantes
    assert len(restantes) < MIN_DIGITOS_IDENTIFICADOR, (texto, redactado)


# Feature: cima-plataforma, Property 9: No fuga de PII hacia el modelo.
# Validates: Requirements 3.10, 3.11
@settings(max_examples=100, deadline=None)
@given(dato=_correos(), antes=_ANTES, despues=_DESPUES)
def test_property_9_correo_no_sobrevive_a_la_redaccion(
    dato: tuple[str, str], antes: str, despues: str
) -> None:
    escrito, correo = dato
    try:
        redactado = redactar_pii(_mensaje(antes, escrito, despues)).texto
    except RedaccionPiiError:
        return
    assert correo not in redactado
    assert "@" not in redactado


# --------------------------------------------------------------------------- #
# Nivel de flujo: el modelo nunca recibe el dato
# --------------------------------------------------------------------------- #
class _ModeloQueCaptura:
    """Modelo simulado que guarda el texto que recibe."""

    def __init__(self) -> None:
        self.recibidos: list[str] = []

    async def generate(self, redacted_text: str) -> ModelResult:
        self.recibidos.append(redacted_text)
        return ModelResult(text="te ayudo con eso", model_version="prueba-v1")


# Feature: cima-plataforma, Property 9: No fuga de PII hacia el modelo.
# Validates: Requirements 3.10, 3.11, 14.6
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(dato=st.one_of(_celulares(), _cedulas(), _correos()), antes=_ANTES, despues=_DESPUES)
@pytest.mark.asyncio
async def test_property_9_el_modelo_nunca_recibe_el_dato(
    dato: tuple[str, str], antes: str, despues: str
) -> None:
    escrito, valor = dato
    db = _FakeSession()
    modelo = _ModeloQueCaptura()

    try:
        acuse = await service.encolar_mensaje_texto(
            db, uuid.uuid4(), ChatTextMessageIn(text=_mensaje(antes, escrito, despues))
        )
    except RedaccionPiiError:
        # Req 3.11: si no se puede redactar, no se persiste ni se invoca el modelo.
        assert db.rows == []
        assert modelo.recibidos == []
        return

    await service.procesar_inferencia(db, acuse.id, modelo=modelo)

    persistido = db.rows[0].input_redacted
    for texto in [persistido, *modelo.recibidos]:
        assert valor not in texto
        assert valor not in _digitos(texto)


# --------------------------------------------------------------------------- #
# Los montos de dinero se conservan
# --------------------------------------------------------------------------- #
@st.composite
def _montos(draw: st.DrawFn) -> str:
    valor = draw(st.integers(min_value=100_000, max_value=99_000_000))
    con_puntos = f"{valor:,}".replace(",", ".")
    escrito = draw(st.sampled_from([con_puntos, str(valor)]))
    forma = draw(st.sampled_from(["${v}", "$ {v}", "{v} pesos", "{v} COP", "{v} millones"]))
    return forma.format(v=escrito)


@settings(max_examples=200, deadline=None)
@given(monto=_montos(), despues=_DESPUES)
def test_los_montos_de_dinero_se_conservan(monto: str, despues: str) -> None:
    texto = f"me prestaron {monto} para abono{despues}"
    assert redactar_pii(texto).texto == texto


@pytest.mark.parametrize(
    "texto",
    [
        "siembro entre 300 - 400 plantas por hectárea",
        "cosecho 250 . 300 bultos",
        "de 1000  a 2000 kilos",
        "sembré el 12/05/2024",
    ],
)
def test_rangos_y_fechas_llegan_intactos_al_modelo(texto: str) -> None:
    """El detector de celulares no une rangos ni fechas: son útiles para la asesoría."""
    assert redactar_pii(texto).texto == texto
