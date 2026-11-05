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
