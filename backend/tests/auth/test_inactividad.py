"""Pruebas de la expiración de la sesión por inactividad (Req 1.14).

La sesión se mantiene con una ventana deslizante: cada petición autenticada
renueva las cookies (access ≤ 15 min y refresh a 30 min), conservando la hora del
ingreso para no pasar el tope absoluto (14 días). Si pasan más de 30 min sin
actividad, el refresh vence y `/api/v1/auth/refresco` responde 401.

Las de extremo a extremo usan la app real con `TestClient`. La cookie se envía en
el encabezado `Cookie`, porque las cookies `Secure` no viajan por http y aquí se
quiere probar el servidor, no el navegador. No requieren base de datos: las rutas
usadas (`/sesion`, `/refresco`, `/salir`, `/health`) no la consultan.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from app.auth import tokens
from app.auth.cookies import ACCESS_COOKIE, REFRESH_COOKIE
from app.common.config import get_settings
from app.main import app

_CFG = get_settings()
_ACCESS = _CFG.access_token_ttl_seconds  # 900
_INACTIVIDAD = _CFG.session_inactivity_seconds  # 1800
_TOPE = _CFG.refresh_token_ttl_seconds  # 14 días
# Margen alrededor de los bordes exactos para no depender del reloj de la prueba.
_MARGEN = 5

cliente = TestClient(app)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _set_cookies(respuesta) -> list[str]:
    return respuesta.headers.get_list("set-cookie")


def _cookie(respuesta, nombre: str) -> str | None:
    """Devuelve el encabezado Set-Cookie completo de `nombre`, o None."""
    for valor in _set_cookies(respuesta):
        if valor.startswith(f"{nombre}="):
            return valor
    return None


def _valor(set_cookie: str) -> str:
    return set_cookie.split(";", 1)[0].split("=", 1)[1]


def _max_age(set_cookie: str) -> int:
    for parte in set_cookie.split(";"):
        clave, _, valor = parte.strip().partition("=")
        if clave.lower() == "max-age":
            return int(valor)
    raise AssertionError(f"sin Max-Age: {set_cookie}")


def _es_valido(token: str, tipo: str) -> bool:
    try:
        tokens.decodificar_sesion(token, tipo)
        return True
    except tokens.TokenInvalidoError:
        return False


# --------------------------------------------------------------------------- #
# Reglas de vida de los tokens (propiedades)
# --------------------------------------------------------------------------- #
@settings(max_examples=100, deadline=None)
@given(
    segundos_inactivo=st.integers(min_value=0, max_value=2 * _INACTIVIDAD).filter(
        lambda s: abs(s - _ACCESS) > _MARGEN and abs(s - _INACTIVIDAD) > _MARGEN
    )
)
def test_property_inactividad_invalida_la_sesion_a_los_30_minutos(
    segundos_inactivo: int,
) -> None:
    """Para todo tiempo sin actividad: el access sirve < 15 min y el refresh < 30 min.

    Con más de 30 min sin actividad ningún token de la sesión sirve y hay que
    volver a autenticarse (Req 1.14). Entre 15 y 30 min el access ya venció pero
    el refresh permite renovar sin pedir la Clave (Req 2.6).
    """
    ultima_actividad = _ahora() - timedelta(seconds=segundos_inactivo)
    sesion = tokens.emitir_sesion(uuid.uuid4(), ahora=ultima_actividad)

    assert _es_valido(sesion.access_token, tokens.TOKEN_TYPE_ACCESS) == (
        segundos_inactivo < _ACCESS
    )
    assert _es_valido(sesion.refresh_token, tokens.TOKEN_TYPE_REFRESH) == (
        segundos_inactivo < _INACTIVIDAD
    )


@settings(max_examples=100, deadline=None)
@given(edad_sesion=st.integers(min_value=0, max_value=_TOPE + 3_600))
def test_property_vida_del_refresh_nunca_pasa_la_inactividad_ni_el_tope(
    edad_sesion: int,
) -> None:
    """La vida del refresh es min(30 min, lo que le queda a la sesión), nunca negativa."""
    ahora = _ahora()
    auth_time = ahora - timedelta(seconds=edad_sesion)

    vida = tokens.vida_refresh_segundos(auth_time, ahora)

    assert vida == max(0, min(_INACTIVIDAD, _TOPE - edad_sesion))
    assert tokens.sesion_vencida(auth_time, ahora) == (edad_sesion >= _TOPE)


def test_la_renovacion_conserva_la_hora_del_ingreso() -> None:
    ingreso = _ahora() - timedelta(hours=3)
    sesion = tokens.emitir_sesion(uuid.uuid4(), auth_time=ingreso)

    for token, tipo in (
        (sesion.access_token, tokens.TOKEN_TYPE_ACCESS),
        (sesion.refresh_token, tokens.TOKEN_TYPE_REFRESH),
    ):
        assert tokens.decodificar_sesion(token, tipo).auth_time == ingreso.replace(
            microsecond=0
        )


def test_refresh_vencido_se_distingue_como_expirado() -> None:
    """El refresh vencido lanza `TokenExpiradoError` (registro interno de inactividad)."""
    hace = _ahora() - timedelta(seconds=_INACTIVIDAD + 60)
    refresh = tokens.crear_refresh_token(uuid.uuid4(), ahora=hace)
    with pytest.raises(tokens.TokenExpiradoError):
        tokens.decodificar_sesion(refresh, tokens.TOKEN_TYPE_REFRESH)


# --------------------------------------------------------------------------- #
# Middleware de actividad (extremo a extremo)
# --------------------------------------------------------------------------- #
def test_peticion_autenticada_renueva_las_cookies_con_ventana_de_30_min() -> None:
    pid = uuid.uuid4()
    ingreso = _ahora() - timedelta(hours=2)
    access = tokens.crear_access_token(pid, auth_time=ingreso)

    respuesta = cliente.get("/api/v1/auth/sesion", headers={"Cookie": f"{ACCESS_COOKIE}={access}"})

    assert respuesta.status_code == 200
    nuevo_access = _cookie(respuesta, ACCESS_COOKIE)
    nuevo_refresh = _cookie(respuesta, REFRESH_COOKIE)
    assert nuevo_access is not None and nuevo_refresh is not None
    # La cookie del refresh dura exactamente la ventana de inactividad.
    assert _max_age(nuevo_refresh) == _INACTIVIDAD
    assert _max_age(nuevo_access) == _ACCESS
    assert "path=/api/v1/auth" in nuevo_refresh.lower()
    for cabecera in (nuevo_access, nuevo_refresh):
        minusculas = cabecera.lower()
        assert "httponly" in minusculas and "samesite" in minusculas
    # El refresh nuevo es del mismo titular y conserva la hora del ingreso.
    datos = tokens.decodificar_sesion(_valor(nuevo_refresh), tokens.TOKEN_TYPE_REFRESH)
    assert datos.profile_id == pid
    assert datos.auth_time == ingreso.replace(microsecond=0)


def test_cerca_del_tope_el_refresh_se_recorta_a_lo_que_queda() -> None:
    restante = 600
    ingreso = _ahora() - timedelta(seconds=_TOPE - restante)
    access = tokens.crear_access_token(uuid.uuid4(), auth_time=ingreso)

    respuesta = cliente.get("/api/v1/auth/sesion", headers={"Cookie": f"{ACCESS_COOKIE}={access}"})

    refresh = _cookie(respuesta, REFRESH_COOKIE)
    assert refresh is not None
    assert 0 < _max_age(refresh) <= restante


def test_sesion_en_su_tope_absoluto_no_se_renueva() -> None:
    ingreso = _ahora() - timedelta(seconds=_TOPE + 60)
    access = tokens.crear_access_token(uuid.uuid4(), auth_time=ingreso)

    respuesta = cliente.get("/api/v1/auth/sesion", headers={"Cookie": f"{ACCESS_COOKIE}={access}"})

    assert _cookie(respuesta, ACCESS_COOKIE) is None
    assert _cookie(respuesta, REFRESH_COOKIE) is None


def test_sin_cookie_no_se_emite_sesion() -> None:
    respuesta = cliente.get("/api/v1/health")
    assert respuesta.status_code == 200
    assert _cookie(respuesta, ACCESS_COOKIE) is None
    assert _cookie(respuesta, REFRESH_COOKIE) is None


def test_token_invalido_no_se_renueva() -> None:
    access = tokens.crear_access_token(uuid.uuid4())
    cabecera, carga, firma = access.split(".")
    alterado = f"{cabecera}.{carga}.{'A' if firma[0] != 'A' else 'B'}{firma[1:]}"

    respuesta = cliente.get("/api/v1/auth/sesion", headers={"Cookie": f"{ACCESS_COOKIE}={alterado}"})

    assert respuesta.status_code == 403
    assert _cookie(respuesta, ACCESS_COOKIE) is None
    assert _cookie(respuesta, REFRESH_COOKIE) is None


def test_access_vencido_no_se_renueva_y_responde_403() -> None:
    """Pasados 15 min el access ya no sirve; la renovación queda a cargo de /refresco."""
    hace = _ahora() - timedelta(seconds=_ACCESS + 60)
    access = tokens.crear_access_token(uuid.uuid4(), ahora=hace)

    respuesta = cliente.get("/api/v1/auth/sesion", headers={"Cookie": f"{ACCESS_COOKIE}={access}"})

    assert respuesta.status_code == 403
    assert _cookie(respuesta, ACCESS_COOKIE) is None


def test_salir_no_vuelve_a_crear_la_sesion() -> None:
    """El middleware no pisa el borrado de cookies del cierre de sesión."""
    access = tokens.crear_access_token(uuid.uuid4())

    respuesta = cliente.post("/api/v1/auth/salir", headers={"Cookie": f"{ACCESS_COOKIE}={access}"})

    assert respuesta.status_code == 204
    cookies_access = [c for c in _set_cookies(respuesta) if c.startswith(f"{ACCESS_COOKIE}=")]
    assert len(cookies_access) == 1
    assert _max_age(cookies_access[0]) == 0


# --------------------------------------------------------------------------- #
# /api/v1/auth/refresco
# --------------------------------------------------------------------------- #
def test_refresco_dentro_de_la_ventana_renueva_y_conserva_el_ingreso() -> None:
    pid = uuid.uuid4()
    ingreso = _ahora() - timedelta(days=1)
    # Última actividad hace 20 min: el access ya venció, el refresh no.
    ultima = _ahora() - timedelta(minutes=20)
    refresh = tokens.crear_refresh_token(pid, auth_time=ingreso, ahora=ultima)

    respuesta = cliente.post(
        "/api/v1/auth/refresco", headers={"Cookie": f"{REFRESH_COOKIE}={refresh}"}
    )

    assert respuesta.status_code == 200
    nuevo = _cookie(respuesta, REFRESH_COOKIE)
    assert nuevo is not None and _max_age(nuevo) == _INACTIVIDAD
    datos = tokens.decodificar_sesion(_valor(nuevo), tokens.TOKEN_TYPE_REFRESH)
    assert datos.profile_id == pid
    assert datos.auth_time == ingreso.replace(microsecond=0)
    # Se rota: el refresh nuevo es distinto del que se envió.
    assert _valor(nuevo) != refresh


def test_refresco_tras_mas_de_30_min_inactivo_exige_ingresar_de_nuevo() -> None:
    ultima = _ahora() - timedelta(seconds=_INACTIVIDAD + 60)
    refresh = tokens.crear_refresh_token(uuid.uuid4(), ahora=ultima)

    respuesta = cliente.post(
        "/api/v1/auth/refresco", headers={"Cookie": f"{REFRESH_COOKIE}={refresh}"}
    )

    assert respuesta.status_code == 401
    assert _cookie(respuesta, ACCESS_COOKIE) is None
    # Mensaje genérico: no revela que la causa fue la inactividad.
    assert "detail" in respuesta.json()


def test_refresco_con_sesion_en_su_tope_absoluto_se_rechaza() -> None:
    ingreso = _ahora() - timedelta(seconds=_TOPE + 60)
    refresh = tokens.crear_refresh_token(uuid.uuid4(), auth_time=ingreso)

    respuesta = cliente.post(
        "/api/v1/auth/refresco", headers={"Cookie": f"{REFRESH_COOKIE}={refresh}"}
    )

    assert respuesta.status_code == 401
    assert _cookie(respuesta, ACCESS_COOKIE) is None


def test_refresco_no_acepta_un_access_token() -> None:
    access = tokens.crear_access_token(uuid.uuid4())
    respuesta = cliente.post(
        "/api/v1/auth/refresco", headers={"Cookie": f"{REFRESH_COOKIE}={access}"}
    )
    assert respuesta.status_code == 401
