"""Pruebas de tokens de sesión y cookies seguras.

Feature: cima-plataforma, Property 6: Propiedades del token de sesión.

Verifican que el access token no exceda 900 s de vida y que las cookies de
sesión lleven los atributos Secure, HttpOnly y SameSite (Req 1.10, 1.11).
Son pruebas puras: no requieren base de datos.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import jwt
from fastapi import Response
from hypothesis import given, settings
from hypothesis import strategies as st

from app.auth import tokens
from app.auth.cookies import ACCESS_COOKIE, set_session_cookies
from app.common.config import get_settings

_SECRET = get_settings().session_secret


def _set_cookie_blob(response: Response) -> str:
    """Devuelve en minúsculas todos los encabezados Set-Cookie de la respuesta."""
    headers = [v.decode() for (k, v) in response.raw_headers if k == b"set-cookie"]
    return " ".join(headers).lower()


# Feature: cima-plataforma, Property 6: Propiedades del token de sesión.
# Validates: Requirements 1.10
@settings(max_examples=100, deadline=None)
@given(seed=st.uuids())
def test_property_6_access_token_vida_corta_y_cookies_seguras(seed: uuid.UUID) -> None:
    """El access token dura <= 900 s y las cookies tienen Secure/HttpOnly/SameSite."""
    # Given un access token recién emitido para un perfil
    token = tokens.crear_access_token(seed)
    payload = jwt.decode(
        token,
        _SECRET,
        algorithms=["HS256"],
        issuer=get_settings().jwt_issuer,
        options={"require": ["exp", "iat", "sub"]},
    )

    # Then su vida (exp - iat) no excede 900 segundos (Req 1.11)
    vida = payload["exp"] - payload["iat"]
    assert vida <= 900
    # And el exp es futuro respecto a ahora
    assert payload["exp"] > datetime.now(timezone.utc).timestamp()
    # And el sub corresponde al perfil
    assert payload["sub"] == str(seed)

    # When se setean las cookies de sesión en una respuesta
    response = Response()
    set_session_cookies(response, access_token=token, refresh_token="dummy.refresh.token")
    cookies_blob = _set_cookie_blob(response)

    # Then la cookie de access está presente con los atributos de seguridad
    assert ACCESS_COOKIE in cookies_blob
    assert "httponly" in cookies_blob
    assert "secure" in cookies_blob
    assert "samesite" in cookies_blob


def test_access_y_refresh_tienen_tipos_distintos() -> None:
    """Un access token no se acepta donde se exige un refresh token, y viceversa."""
    pid = uuid.uuid4()
    access = tokens.crear_access_token(pid)
    refresh = tokens.crear_refresh_token(pid)

    # El decodificador exige el tipo correcto.
    assert tokens.decodificar_token(access, tokens.TOKEN_TYPE_ACCESS) == pid
    assert tokens.decodificar_token(refresh, tokens.TOKEN_TYPE_REFRESH) == pid

    # Cruzar los tipos falla.
    for token, tipo_incorrecto in (
        (access, tokens.TOKEN_TYPE_REFRESH),
        (refresh, tokens.TOKEN_TYPE_ACCESS),
    ):
        try:
            tokens.decodificar_token(token, tipo_incorrecto)
            raise AssertionError("se esperaba TokenInvalidoError por tipo cruzado")
        except tokens.TokenInvalidoError:
            pass


def test_token_con_firma_alterada_es_rechazado() -> None:
    """Un token manipulado (firma inválida) se rechaza (integridad, A02)."""
    pid = uuid.uuid4()
    token = tokens.crear_access_token(pid)
    # Alterar el último carácter del token invalida la firma.
    alterado = token[:-1] + ("a" if token[-1] != "a" else "b")
    try:
        tokens.decodificar_token(alterado, tokens.TOKEN_TYPE_ACCESS)
        raise AssertionError("se esperaba TokenInvalidoError por firma inválida")
    except tokens.TokenInvalidoError:
        pass


def test_rotacion_emite_refresh_tokens_distintos() -> None:
    """Dos refresh tokens del mismo perfil difieren (jti único por emisión)."""
    pid = uuid.uuid4()
    r1 = tokens.crear_refresh_token(pid)
    r2 = tokens.crear_refresh_token(pid)
    assert r1 != r2
