"""Pruebas de restauración de sesión (`GET /api/v1/auth/sesion`).

Verifican el comportamiento de la dependencia de identidad que respalda la
restauración de sesión (Req 2.6, 2.7): con un access token válido devuelve el
`profile_id`; sin cookie o con token inválido/expirado rechaza con error de
autorización (para que el cliente redirija al login conservando el destino).
Son pruebas puras: no requieren base de datos.
"""
from __future__ import annotations

import uuid

import pytest

from app.auth import tokens
from app.common.errors import ForbiddenError
from app.common.security import get_current_user_id


@pytest.mark.asyncio
async def test_sesion_valida_restaura_identidad() -> None:
    """Un access token vigente resuelve el `profile_id` del titular (Req 2.6)."""
    pid = uuid.uuid4()
    access = tokens.crear_access_token(pid)
    # La dependencia recibe el valor de la cookie `cima_access`.
    resuelto = await get_current_user_id(cima_access=access)
    assert resuelto == pid


@pytest.mark.asyncio
async def test_sesion_sin_cookie_es_rechazada() -> None:
    """Sin cookie de sesión se rechaza con ForbiddenError (Req 2.7)."""
    with pytest.raises(ForbiddenError):
        await get_current_user_id(cima_access=None)


@pytest.mark.asyncio
async def test_sesion_con_refresh_token_en_cookie_de_acceso_es_rechazada() -> None:
    """Un refresh token no sirve como access token: el tipo debe coincidir."""
    pid = uuid.uuid4()
    refresh = tokens.crear_refresh_token(pid)
    with pytest.raises(ForbiddenError):
        await get_current_user_id(cima_access=refresh)


@pytest.mark.asyncio
async def test_sesion_con_token_corrupto_es_rechazada() -> None:
    """Un token con firma alterada se rechaza (integridad, Req 2.7)."""
    pid = uuid.uuid4()
    access = tokens.crear_access_token(pid)
    # Se altera el PRIMER carácter de la firma. El último no sirve: en base64url
    # solo aporta 4 bits útiles y 2 de relleno, así que cambiarlo (p. ej. "Y"/"Z"
    # por "a") puede dejar los mismos bytes y la firma seguir válida, lo que
    # hacía que esta prueba fallara de forma intermitente.
    cabecera, carga, firma = access.split(".")
    otro = "A" if firma[0] != "A" else "B"
    corrupto = f"{cabecera}.{carga}.{otro}{firma[1:]}"
    with pytest.raises(ForbiddenError):
        await get_current_user_id(cima_access=corrupto)
