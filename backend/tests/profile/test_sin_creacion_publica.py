"""Regresión: no existe una creación pública de Perfil (Req 1.7, 9.4).

`POST /api/v1/perfiles` era público y respondía 422 si el teléfono ya tenía
cuenta y 500 si no (intentaba crear el Perfil sin el hash de la Clave). Esa
diferencia permitía, sin sesión, averiguar qué celulares están registrados, lo
que contradice el error indistinguible del ingreso (Req 1.7). La ruta se quitó:
el Perfil nace con el registro (`POST /api/v1/auth/registro`).

Estas pruebas fijan que la ruta no exista y que la respuesta no dependa del
teléfono enviado. No requieren base de datos: la ruta ya no llega a consultarla.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth import tokens
from app.auth.cookies import ACCESS_COOKIE
from app.main import app

cliente = TestClient(app)

_RUTA = "/api/v1/perfiles"
# Teléfonos sintéticos: uno con forma de "registrado" y otro "nuevo". Ya no hay
# forma de que la API los distinga, así que el resultado debe ser idéntico.
_TELEFONOS = ("3001234567", "3000000001")


def _crear(telefono: str, cookie: str | None = None):
    cabeceras = {"Cookie": cookie} if cookie else {}
    return cliente.post(
        _RUTA,
        json={"phone": telefono, "activity_type": "cafe", "geo_zone": "Huila"},
        headers=cabeceras,
    )


@pytest.mark.parametrize("telefono", _TELEFONOS)
def test_crear_perfil_publico_ya_no_existe(telefono: str) -> None:
    respuesta = _crear(telefono)

    # Ni creación (2xx), ni validación (422), ni error interno (500).
    assert respuesta.status_code in (404, 405)


def test_la_respuesta_no_revela_si_el_telefono_existe() -> None:
    """Misma respuesta para cualquier teléfono: no sirve para averiguar cuentas."""
    registrado, nuevo = (_crear(t) for t in _TELEFONOS)

    assert registrado.status_code == nuevo.status_code
    assert registrado.json() == nuevo.json()


def test_tampoco_existe_con_sesion() -> None:
    """Con una sesión válida tampoco hay creación: el Perfil ya existe desde el registro."""
    access = tokens.crear_access_token(uuid.uuid4())

    respuesta = _crear(_TELEFONOS[0], cookie=f"{ACCESS_COOKIE}={access}")

    assert respuesta.status_code in (404, 405)


def test_el_contrato_openapi_no_declara_la_creacion() -> None:
    rutas = app.openapi()["paths"]

    assert "post" not in rutas.get(_RUTA, {})
    # Siguen las rutas del Perfil propio.
    assert "get" in rutas["/api/v1/perfiles/me"]
    assert "put" in rutas["/api/v1/perfiles/{perfil_id}"]
