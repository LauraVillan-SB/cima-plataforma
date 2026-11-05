"""Cliente HTTP seguro con control de SSRF para consumo externo.

Toda llamada saliente se permite si y solo si: (1) el esquema es HTTPS, (2) el
dominio está en la allowlist y (3) el destino no resuelve a una IP privada o de
enlace local. En cualquier otro caso se bloquea SIN transmitir datos y se
registra el intento con su Correlation-ID (Property 34).

Requisitos: 10.4, 10.5 (OWASP A10 SSRF). Dependencias externas se envuelven
además con el circuit breaker de `app/common/resilience.py` (Req 11.5, 11.6).
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urlsplit

import httpx

from app.common.config import get_settings
from app.common.logging import log_event

logger = logging.getLogger("cima.http")


class SsrfBlockedError(Exception):
    """La URL de destino fue bloqueada por la política de SSRF."""


def _dominios_permitidos() -> frozenset[str]:
    """Allowlist de dominios normalizada desde la configuración."""
    crudo = get_settings().http_allowlist_domains or ""
    return frozenset(
        d.strip().lower() for d in crudo.split(",") if d.strip()
    )


def _es_ip_bloqueada(ip: str) -> bool:
    """Indica si una IP es privada, loopback, link-local o reservada.

    Bloquea 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 y
    169.254.0.0/16 (incluye 169.254.169.254, metadatos de nube), entre otras.
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        # Si no es una IP válida, se trata como no resoluble → bloquear.
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def _resuelve_a_ip_bloqueada(host: str) -> bool:
    """Resuelve el host y bloquea si CUALQUIER dirección es privada/link-local.

    Resolver antes de conectar evita el rebinding a direcciones internas: si el
    DNS devuelve una IP interna, se bloquea sin transmitir.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        # No resoluble → bloquear por seguridad.
        return True
    for info in infos:
        ip = info[4][0]
        if _es_ip_bloqueada(ip):
            return True
    return False


def url_permitida(url: str) -> bool:
    """Evalúa la política de SSRF para una URL, sin realizar la petición.

    Permite si y solo si: esquema HTTPS, dominio en la allowlist y el host no
    resuelve a una IP privada/link-local (Property 34).
    """
    partes = urlsplit(url)
    if partes.scheme != "https":
        return False
    host = (partes.hostname or "").lower()
    if not host or host not in _dominios_permitidos():
        return False
    if _resuelve_a_ip_bloqueada(host):
        return False
    return True


def _verificar_o_bloquear(url: str) -> None:
    """Valida la URL contra la política; registra y lanza si está bloqueada."""
    if not url_permitida(url):
        # No se incluye la URL completa para no filtrar posibles secretos en
        # query string; solo el host, útil para auditoría (Req 10.5).
        host = (urlsplit(url).hostname or "desconocido").lower()
        log_event(logger, "ssrf_bloqueado", host=host)
        raise SsrfBlockedError("destino no permitido por la politica de SSRF")


def crear_cliente() -> httpx.AsyncClient:
    """Crea un `AsyncClient` con timeout bajo y límite de redirecciones.

    El llamador debe usar `solicitar` para que la verificación de SSRF se aplique
    también a la URL final tras redirecciones.
    """
    settings = get_settings()
    return httpx.AsyncClient(
        timeout=settings.http_timeout_seconds,
        follow_redirects=True,
        max_redirects=settings.http_max_redirects,
    )


async def solicitar(
    cliente: httpx.AsyncClient,
    metodo: str,
    url: str,
    **kwargs: object,
) -> httpx.Response:
    """Realiza una petición solo si la URL pasa la política de SSRF.

    Verifica la URL antes de transmitir cualquier dato; si está bloqueada,
    lanza `SsrfBlockedError` sin realizar la llamada.
    """
    _verificar_o_bloquear(url)
    respuesta = await cliente.request(metodo, url, **kwargs)
    # Verifica también el destino final tras posibles redirecciones.
    _verificar_o_bloquear(str(respuesta.url))
    return respuesta
