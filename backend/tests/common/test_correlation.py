"""Pruebas de propiedad de la propagación del Correlation-ID (Tarea 3.5).

Feature: cima-plataforma, Property 35: Propagación del Correlation-ID.
Validates: Requirements 11.1

*Para toda* petición entrante, cada invocación saliente asociada incluye un
Correlation-ID; si la petición entrante ya traía uno, se conserva sin cambios a lo
largo de toda la cadena. Se verifica la cadena completa con una app mínima que
usa el middleware y los manejadores de error reales: el id de la respuesta, el
del contexto de la petición, el del cuerpo de error y el de la llamada saliente
hecha con `http_client` (contra un transporte simulado, sin red).

Además, el id recibido se valida (Zero Trust Input): uno con caracteres no
permitidos o demasiado largo no se reutiliza y se reemplaza por un UUID v4.
"""
from __future__ import annotations

import re
import string
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from app.common import http_client
from app.common.correlation import (
    CORRELATION_HEADER,
    CorrelationIdMiddleware,
    es_correlation_id_valido,
    get_correlation_id,
)
from app.common.errors import NotFoundError, register_error_handlers

_UUID_V4 = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
_DESTINO = "https://sostenibilidadbolivar.com/servicio"
_IP_PUBLICA = [("", "", "", "", ("93.184.216.34", 0))]
# Valor ficticio, no es un secreto.
_TOKEN = "token-de-prueba"

# Cabeceras que recibió el "tercero" simulado en cada llamada saliente.
_recibidas: list[httpx.Headers] = []


def _tercero(request: httpx.Request) -> httpx.Response:
    _recibidas.append(request.headers)
    return httpx.Response(200, json={"ok": True})


app = FastAPI()
app.add_middleware(CorrelationIdMiddleware)
register_error_handlers(app)


@app.get("/eco")
async def _eco() -> dict[str, str]:
    return {"contexto": get_correlation_id()}


@app.get("/falla")
async def _falla() -> None:
    raise NotFoundError(internal_detail="prueba")


@app.get("/saliente")
async def _saliente() -> dict[str, str]:
    cliente = http_client.crear_cliente(transport=httpx.MockTransport(_tercero))
    async with cliente:
        await http_client.solicitar(cliente, "GET", _DESTINO, token=_TOKEN)
    return {"contexto": get_correlation_id()}


cliente_app = TestClient(app)

# Ids con la forma admitida: se deben conservar sin cambios en toda la cadena.
_ids_validos = st.from_regex(r"[A-Za-z0-9._:-]{1,128}", fullmatch=True)
# Ids con al menos un carácter no admitido (ASCII imprimible, sin espacios en los
# bordes porque el middleware los recorta) o demasiado largos.
_no_admitidos = "!\"#$%&'()*+,/;<=>?@[\\]^`{|}~"
_ids_con_caracter_invalido = st.builds(
    lambda a, x, b: a + x + b,
    st.text(alphabet=string.ascii_letters, max_size=10),
    st.sampled_from(list(_no_admitidos)),
    st.text(alphabet=string.ascii_letters, max_size=10),
)
_ids_largos = st.text(alphabet=string.ascii_letters + string.digits, min_size=129, max_size=300)


# --------------------------------------------------------------------------- #
# Property 35
# --------------------------------------------------------------------------- #
# Feature: cima-plataforma, Property 35: Propagación del Correlation-ID.
# Validates: Requirements 11.1
@settings(max_examples=100, deadline=None)
@given(entrante=_ids_validos)
def test_property_35_id_entrante_se_conserva_en_toda_la_cadena(entrante: str) -> None:
    _recibidas.clear()
    cabecera = {CORRELATION_HEADER: entrante}

    with patch.object(http_client.socket, "getaddrinfo", return_value=_IP_PUBLICA):
        saliente = cliente_app.get("/saliente", headers=cabecera)
    error = cliente_app.get("/falla", headers=cabecera)

    # Respuesta y contexto de la petición conservan el id tal cual.
    assert saliente.headers[CORRELATION_HEADER] == entrante
    assert saliente.json()["contexto"] == entrante
    # La llamada saliente lleva el mismo id.
    assert len(_recibidas) == 1
    assert _recibidas[0][CORRELATION_HEADER] == entrante
    # El cuerpo de error también lo informa (Req 11.2).
    assert error.status_code == 404
    assert error.json()["correlation_id"] == entrante
    assert error.headers[CORRELATION_HEADER] == entrante


# Feature: cima-plataforma, Property 35: Propagación del Correlation-ID.
# Validates: Requirements 11.1
@settings(max_examples=100, deadline=None)
@given(llamadas=st.integers(min_value=1, max_value=3))
def test_property_35_sin_id_entrante_se_genera_uno_y_se_propaga(llamadas: int) -> None:
    """Sin id entrante se genera un UUID v4 distinto por petición y viaja a la saliente."""
    vistos: set[str] = set()
    for _ in range(llamadas):
        _recibidas.clear()
        with patch.object(http_client.socket, "getaddrinfo", return_value=_IP_PUBLICA):
            respuesta = cliente_app.get("/saliente")
        generado = respuesta.headers[CORRELATION_HEADER]
        assert _UUID_V4.fullmatch(generado)
        assert respuesta.json()["contexto"] == generado
        assert _recibidas[0][CORRELATION_HEADER] == generado
        vistos.add(generado)
    assert len(vistos) == llamadas


@settings(max_examples=100, deadline=None)
@given(entrante=st.one_of(_ids_con_caracter_invalido, _ids_largos))
def test_id_entrante_invalido_se_reemplaza_por_uno_nuevo(entrante: str) -> None:
    """Un id con caracteres no admitidos o demasiado largo no se reutiliza."""
    assert not es_correlation_id_valido(entrante)

    respuesta = cliente_app.get("/eco", headers={CORRELATION_HEADER: entrante})

    asignado = respuesta.headers[CORRELATION_HEADER]
    assert asignado != entrante
    assert _UUID_V4.fullmatch(asignado)
    assert respuesta.json()["contexto"] == asignado


def test_espacios_en_los_bordes_se_recortan() -> None:
    respuesta = cliente_app.get("/eco", headers={CORRELATION_HEADER: "  abc-123  "})
    assert respuesta.headers[CORRELATION_HEADER] == "abc-123"


@pytest.mark.asyncio
async def test_llamada_saliente_fuera_de_una_peticion_lleva_un_id_generado() -> None:
    """Un worker sin petición entrante igual envía un Correlation-ID (UUID v4)."""
    _recibidas.clear()
    cliente = http_client.crear_cliente(transport=httpx.MockTransport(_tercero))
    with patch.object(http_client.socket, "getaddrinfo", return_value=_IP_PUBLICA):
        async with cliente:
            await http_client.solicitar(cliente, "GET", _DESTINO, token=_TOKEN)
    assert _UUID_V4.fullmatch(_recibidas[0][CORRELATION_HEADER])


@pytest.mark.asyncio
async def test_id_fijado_por_el_llamador_se_respeta() -> None:
    _recibidas.clear()
    cliente = http_client.crear_cliente(transport=httpx.MockTransport(_tercero))
    with patch.object(http_client.socket, "getaddrinfo", return_value=_IP_PUBLICA):
        async with cliente:
            await http_client.solicitar(
                cliente, "GET", _DESTINO, token=_TOKEN, headers={CORRELATION_HEADER: "fijado-1"}
            )
    assert _recibidas[0][CORRELATION_HEADER] == "fijado-1"
