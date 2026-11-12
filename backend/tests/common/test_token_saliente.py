"""Pruebas del token firmado en las llamadas salientes (Tarea 9.1).

Req 10.4: las llamadas salientes van autenticadas con token firmado, solo sobre
HTTPS y hacia dominios de la allowlist. Se verifica contra un transporte simulado
(sin red) que:

- el token llega al destino como `Authorization: Bearer` y prevalece sobre el que
  traiga el llamador;
- un token ausente o con formato inválido se rechaza sin transmitir y sin
  revelarlo en el mensaje de error;
- una redirección a OTRO origen no reenvía el token y una dentro del mismo
  origen sí lo conserva;
- el token no aparece en ningún log.

Validates: Requirements 10.4
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import httpx
import pytest

from app.common import http_client

# Valor ficticio, no es un secreto.
_TOKEN = "token-de-prueba.firma_ficticia-123"
_INICIO = "https://sostenibilidadbolivar.com/inicio"
_MISMO_ORIGEN = "https://sostenibilidadbolivar.com/final"
_OTRO_ORIGEN = "https://api.sostenibilidadbolivar.com/final"
_IP_PUBLICA = [("", "", "", "", ("93.184.216.34", 0))]


def _transporte(recibidas: list[httpx.Request], redirigir_a: str | None = None) -> httpx.MockTransport:
    """Registra cada petición recibida; si se indica, `_INICIO` redirige a `redirigir_a`."""

    def manejar(request: httpx.Request) -> httpx.Response:
        recibidas.append(request)
        if redirigir_a and str(request.url) == _INICIO:
            return httpx.Response(302, headers={"Location": redirigir_a})
        return httpx.Response(200, json={"ok": True})

    return httpx.MockTransport(manejar)


async def _llamar(recibidas: list[httpx.Request], redirigir_a: str | None = None, **kwargs: object) -> httpx.Response:
    cliente = http_client.crear_cliente(transport=_transporte(recibidas, redirigir_a))
    with patch.object(http_client.socket, "getaddrinfo", return_value=_IP_PUBLICA):
        async with cliente:
            return await http_client.solicitar(cliente, "GET", _INICIO, **kwargs)


@pytest.fixture
def allowlist_con_subdominio():
    """Permite también `api.sostenibilidadbolivar.com` (otro origen permitido)."""
    with patch.dict(
        "os.environ",
        {"HTTP_ALLOWLIST_DOMAINS": "sostenibilidadbolivar.com,api.sostenibilidadbolivar.com"},
    ):
        http_client.get_settings.cache_clear()
        try:
            yield
        finally:
            http_client.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_el_token_llega_al_destino_como_bearer() -> None:
    recibidas: list[httpx.Request] = []
    respuesta = await _llamar(recibidas, token=_TOKEN)

    assert respuesta.status_code == 200
    assert len(recibidas) == 1
    assert recibidas[0].headers["Authorization"] == f"Bearer {_TOKEN}"


@pytest.mark.asyncio
@pytest.mark.parametrize("nombre", ["Authorization", "authorization", "AUTHORIZATION"])
async def test_el_token_prevalece_sobre_el_authorization_del_llamador(nombre: str) -> None:
    recibidas: list[httpx.Request] = []
    await _llamar(recibidas, token=_TOKEN, headers={nombre: "Bearer otro", "X-Extra": "1"})

    assert recibidas[0].headers.get_list("Authorization") == [f"Bearer {_TOKEN}"]
    # Las demás cabeceras del llamador se conservan.
    assert recibidas[0].headers["X-Extra"] == "1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalido",
    [
        "",
        "   ",
        "con espacio",
        "abc\r\nX-Inyectada: 1",  # inyección de cabeceras
        "abc\n",
        "ñandú",
        "a" * 4097,
        None,
        123,
    ],
)
async def test_token_ausente_o_invalido_se_rechaza_sin_transmitir(invalido: object) -> None:
    recibidas: list[httpx.Request] = []
    with pytest.raises(ValueError) as error:
        await _llamar(recibidas, token=invalido)

    assert recibidas == []
    if isinstance(invalido, str) and invalido.strip():
        assert invalido not in str(error.value)


@pytest.mark.asyncio
async def test_sin_token_la_llamada_no_es_posible() -> None:
    recibidas: list[httpx.Request] = []
    with pytest.raises(TypeError):
        await _llamar(recibidas)
    assert recibidas == []


@pytest.mark.asyncio
async def test_redireccion_a_otro_origen_no_reenvia_el_token(allowlist_con_subdominio: None) -> None:
    recibidas: list[httpx.Request] = []
    respuesta = await _llamar(recibidas, redirigir_a=_OTRO_ORIGEN, token=_TOKEN)

    assert respuesta.status_code == 200
    assert [str(r.url) for r in recibidas] == [_INICIO, _OTRO_ORIGEN]
    assert recibidas[0].headers["Authorization"] == f"Bearer {_TOKEN}"
    assert "Authorization" not in recibidas[1].headers


@pytest.mark.asyncio
async def test_redireccion_dentro_del_mismo_origen_conserva_el_token() -> None:
    recibidas: list[httpx.Request] = []
    await _llamar(recibidas, redirigir_a=_MISMO_ORIGEN, token=_TOKEN)

    assert [str(r.url) for r in recibidas] == [_INICIO, _MISMO_ORIGEN]
    assert all(r.headers["Authorization"] == f"Bearer {_TOKEN}" for r in recibidas)


@pytest.mark.asyncio
async def test_el_token_no_aparece_en_los_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    recibidas: list[httpx.Request] = []

    # Llamada exitosa con redirección y llamada bloqueada por SSRF (que sí registra).
    await _llamar(recibidas, redirigir_a=_MISMO_ORIGEN, token=_TOKEN)
    with pytest.raises(http_client.SsrfBlockedError):
        await _llamar(recibidas, redirigir_a="https://169.254.169.254/x", token=_TOKEN)

    assert any(r.getMessage() == "ssrf_bloqueado" for r in caplog.records)
    for registro in caplog.records:
        assert _TOKEN not in registro.getMessage()
        assert _TOKEN not in str(registro.__dict__)
