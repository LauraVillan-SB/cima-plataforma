"""Pruebas de propiedad del control de SSRF (Tarea 9.2).

Property 34: para toda URL de destino, la comunicación se permite si y solo si
el dominio está en la allowlist, el esquema es HTTPS y el destino no resuelve a
una IP privada o de enlace local; en cualquier otro caso se bloquea.

Feature: cima-plataforma, Property 34
Validates: Requirements 10.4, 10.5
"""

from __future__ import annotations

from unittest.mock import patch

from hypothesis import given
from hypothesis import strategies as st

from app.common import http_client


# IPs públicas de ejemplo para simular resolución DNS permitida.
_IP_PUBLICA = [("", "", "", "", ("93.184.216.34", 0))]
# IPs internas que deben bloquearse (loopback, privadas, link-local/metadatos).
_IPS_INTERNAS = ["127.0.0.1", "10.0.0.5", "172.16.0.1", "192.168.1.1", "169.254.169.254"]


def _dns(ip: str):
    """Construye una respuesta de getaddrinfo con una sola IP."""
    return [("", "", "", "", (ip, 0))]


def test_bloquea_esquema_no_https() -> None:
    # Given un dominio permitido pero esquema HTTP (no HTTPS)
    with patch.object(http_client.socket, "getaddrinfo", return_value=_IP_PUBLICA):
        # Then: se bloquea por no ser HTTPS (Req 10.4)
        assert http_client.url_permitida("http://sostenibilidadbolivar.com/x") is False


def test_bloquea_dominio_fuera_de_allowlist() -> None:
    with patch.object(http_client.socket, "getaddrinfo", return_value=_IP_PUBLICA):
        assert http_client.url_permitida("https://malicioso.example/x") is False


def test_permite_dominio_allowlist_https_ip_publica() -> None:
    with patch.object(http_client.socket, "getaddrinfo", return_value=_IP_PUBLICA):
        assert http_client.url_permitida("https://sostenibilidadbolivar.com/ruta") is True


@given(ip=st.sampled_from(_IPS_INTERNAS))
def test_bloquea_ip_privada_o_link_local(ip: str) -> None:
    # Given un dominio permitido y HTTPS, pero que resuelve a una IP interna
    with patch.object(http_client.socket, "getaddrinfo", return_value=_dns(ip)):
        # Then: se bloquea aunque el dominio esté en la allowlist (anti-rebinding)
        assert http_client.url_permitida("https://sostenibilidadbolivar.com/x") is False


@given(
    esquema=st.sampled_from(["http", "https", "ftp", "file"]),
    dominio=st.sampled_from(["sostenibilidadbolivar.com", "evil.example", "localhost"]),
)
def test_property_34_permitido_sii_condiciones(esquema: str, dominio: str) -> None:
    # Resuelve siempre a IP pública para aislar el efecto de esquema+dominio.
    with patch.object(http_client.socket, "getaddrinfo", return_value=_IP_PUBLICA):
        permitido = http_client.url_permitida(f"{esquema}://{dominio}/x")
    esperado = esquema == "https" and dominio == "sostenibilidadbolivar.com"
    assert permitido is esperado


# --------------------------------------------------------------------------- #
# Envío real con redirecciones: el bloqueo ocurre ANTES de transmitir.
# --------------------------------------------------------------------------- #
# Regresión: antes `solicitar` verificaba la URL final DESPUÉS de seguir las
# redirecciones, así que una redirección desde un dominio permitido hacia una
# dirección interna ya se había transmitido cuando se lanzaba el error. Ahora el
# hook `request` verifica cada salto antes de enviarlo.
import httpx  # noqa: E402
import pytest  # noqa: E402

_PERMITIDA = "https://sostenibilidadbolivar.com/inicio"


def _transporte_que_redirige(destino: str, recibidas: list[str]) -> httpx.MockTransport:
    """El dominio permitido redirige a `destino`; registra cada URL que recibe."""

    def manejar(request: httpx.Request) -> httpx.Response:
        recibidas.append(str(request.url))
        if str(request.url) == _PERMITIDA:
            return httpx.Response(302, headers={"Location": destino})
        return httpx.Response(200, json={"ok": True})

    return httpx.MockTransport(manejar)


def _dns_por_host(internos: dict[str, str]):
    """getaddrinfo simulado: IP interna para los hosts indicados, pública para el resto."""

    def resolver(host, *_args, **_kwargs):
        return _dns(internos.get(host, "93.184.216.34"))

    return resolver


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "destino",
    [
        "https://169.254.169.254/latest/meta-data/",  # metadatos de nube por IP
        "http://sostenibilidadbolivar.com/sin-https",  # baja a HTTP
        "https://malicioso.example/robar",  # fuera de la allowlist
    ],
)
async def test_redireccion_a_destino_prohibido_se_bloquea_sin_transmitir(destino: str) -> None:
    recibidas: list[str] = []
    cliente = http_client.crear_cliente(transport=_transporte_que_redirige(destino, recibidas))

    with patch.object(http_client.socket, "getaddrinfo", side_effect=_dns_por_host({})):
        async with cliente:
            with pytest.raises(http_client.SsrfBlockedError):
                await http_client.solicitar(cliente, "GET", _PERMITIDA)

    # Solo llegó la petición al dominio permitido; el destino prohibido nunca la recibió.
    assert recibidas == [_PERMITIDA]


@pytest.mark.asyncio
async def test_redireccion_a_dominio_permitido_que_resuelve_a_ip_interna_se_bloquea() -> None:
    """Rebinding: el nombre está en la allowlist pero su DNS apunta a una IP privada."""
    recibidas: list[str] = []
    interno = "https://api.sostenibilidadbolivar.com/x"
    cliente = http_client.crear_cliente(transport=_transporte_que_redirige(interno, recibidas))

    with patch.dict("os.environ", {"HTTP_ALLOWLIST_DOMAINS": "sostenibilidadbolivar.com,api.sostenibilidadbolivar.com"}):
        http_client.get_settings.cache_clear()
        try:
            with patch.object(
                http_client.socket,
                "getaddrinfo",
                side_effect=_dns_por_host({"api.sostenibilidadbolivar.com": "10.0.0.5"}),
            ):
                async with cliente:
                    with pytest.raises(http_client.SsrfBlockedError):
                        await http_client.solicitar(cliente, "GET", _PERMITIDA)
        finally:
            http_client.get_settings.cache_clear()

    assert recibidas == [_PERMITIDA]


@pytest.mark.asyncio
async def test_redireccion_dentro_del_dominio_permitido_se_sigue() -> None:
    recibidas: list[str] = []
    destino = "https://sostenibilidadbolivar.com/final"
    cliente = http_client.crear_cliente(transport=_transporte_que_redirige(destino, recibidas))

    with patch.object(http_client.socket, "getaddrinfo", side_effect=_dns_por_host({})):
        async with cliente:
            respuesta = await http_client.solicitar(cliente, "GET", _PERMITIDA)

    assert respuesta.status_code == 200
    assert recibidas == [_PERMITIDA, destino]


@pytest.mark.asyncio
async def test_solicitar_rechaza_un_cliente_sin_la_politica_de_ssrf() -> None:
    """Un `httpx.AsyncClient` cualquiera seguiría redirecciones sin verificarlas."""
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))) as crudo:
        with pytest.raises(ValueError):
            await http_client.solicitar(crudo, "GET", _PERMITIDA)
