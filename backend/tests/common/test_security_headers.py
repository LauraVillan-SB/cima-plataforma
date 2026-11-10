"""Pruebas de las cabeceras de seguridad de la API (OWASP A02/A05, tarea 24.1).

Toda respuesta, también las de error, debe llevar HSTS, CSP, nosniff,
X-Frame-Options, Referrer-Policy y Permissions-Policy. La API JSON usa la CSP más
estricta; solo la documentación interactiva usa una CSP acotada a lo que carga.
Se prueba con una app mínima que usa el middleware y los manejadores de error
reales, y con la app de CIMA para las rutas que no tocan la base de datos.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import BaseModel

from app.common.errors import NotFoundError, register_error_handlers
from app.common.security_headers import (
    CABECERAS_BASE,
    CSP_API,
    CSP_DOCS,
    RUTAS_DOCS,
    SecurityHeadersMiddleware,
    cabeceras_para,
)
from app.main import app as app_cima

ESPERADAS = {
    "strict-transport-security",
    "content-security-policy",
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
    "permissions-policy",
}


class _Entrada(BaseModel):
    numero: int


app = FastAPI()
app.add_middleware(SecurityHeadersMiddleware)
register_error_handlers(app)


@app.get("/ok")
async def _ok() -> dict[str, str]:
    return {"estado": "ok"}


@app.get("/dominio")
async def _dominio() -> None:
    raise NotFoundError(internal_detail="prueba")


@app.post("/validacion")
async def _validacion(datos: _Entrada) -> dict[str, int]:
    return {"numero": datos.numero}


@app.get("/explota")
async def _explota() -> None:
    raise RuntimeError("fallo inesperado de prueba")


@app.get("/debil")
async def _debil() -> JSONResponse:
    # Una ruta que intenta poner cabeceras más débiles.
    return JSONResponse(
        {"x": 1},
        headers={"Content-Security-Policy": "default-src *", "X-Frame-Options": "ALLOWALL"},
    )


cliente = TestClient(app, raise_server_exceptions=False)
cliente_cima = TestClient(app_cima)


def _assert_cabeceras_api(respuesta) -> None:
    faltan = ESPERADAS - {k.lower() for k in respuesta.headers}
    assert not faltan, f"faltan cabeceras: {faltan}"
    assert respuesta.headers["content-security-policy"] == CSP_API
    for nombre, valor in CABECERAS_BASE.items():
        assert respuesta.headers[nombre] == valor


@pytest.mark.parametrize(
    ("metodo", "ruta", "cuerpo", "codigo"),
    [
        ("get", "/ok", None, 200),
        ("get", "/dominio", None, 404),
        ("post", "/validacion", {"numero": "no-es-numero"}, 422),
        ("get", "/explota", None, 500),
        ("get", "/no-existe", None, 404),
        ("delete", "/ok", None, 405),
    ],
)
def test_toda_respuesta_lleva_las_cabeceras(metodo: str, ruta: str, cuerpo, codigo: int) -> None:
    respuesta = cliente.request(metodo.upper(), ruta, json=cuerpo)

    assert respuesta.status_code == codigo
    _assert_cabeceras_api(respuesta)


def test_el_500_no_expone_detalles_internos() -> None:
    respuesta = cliente.get("/explota")

    assert respuesta.status_code == 500
    assert "fallo inesperado" not in respuesta.text
    assert "Traceback" not in respuesta.text


def test_una_ruta_no_puede_debilitar_las_cabeceras() -> None:
    respuesta = cliente.get("/debil")

    assert respuesta.headers["content-security-policy"] == CSP_API
    assert respuesta.headers["x-frame-options"] == "DENY"
    # No quedan cabeceras duplicadas con el valor débil.
    assert respuesta.headers.get_list("content-security-policy") == [CSP_API]


@settings(max_examples=100, deadline=None)
@given(ruta=st.from_regex(r"/[a-z0-9/_-]{0,40}", fullmatch=True))
def test_property_solo_la_documentacion_usa_la_csp_relajada(ruta: str) -> None:
    """Para toda ruta, la CSP relajada se usa si y solo si es de la documentación."""
    csp = cabeceras_para(ruta)["Content-Security-Policy"]

    assert csp == (CSP_DOCS if ruta in RUTAS_DOCS else CSP_API)


def test_la_csp_de_la_api_no_permite_cargar_ni_incrustar_nada() -> None:
    directivas = {d.strip().split(" ", 1)[0]: d.strip() for d in CSP_API.split(";")}

    assert directivas["default-src"] == "default-src 'none'"
    assert directivas["frame-ancestors"] == "frame-ancestors 'none'"
    assert "unsafe-inline" not in CSP_API
    assert "*" not in CSP_API


def test_la_csp_de_la_documentacion_no_admite_comodines_ni_marcos() -> None:
    assert "frame-ancestors 'none'" in CSP_DOCS
    assert "unsafe-eval" not in CSP_DOCS
    assert " * " not in f" {CSP_DOCS} "
    assert "http:" not in CSP_DOCS


def test_hsts_no_incluye_preload() -> None:
    """La precarga en los navegadores la decide quien administra el dominio."""
    assert "preload" not in CABECERAS_BASE["Strict-Transport-Security"]


# --------------------------------------------------------------------------- #
# App real de CIMA (rutas que no consultan la base de datos)
# --------------------------------------------------------------------------- #
def test_app_cima_health_lleva_las_cabeceras() -> None:
    respuesta = cliente_cima.get("/api/v1/health")

    assert respuesta.status_code == 200
    _assert_cabeceras_api(respuesta)


def test_app_cima_sin_sesion_lleva_las_cabeceras() -> None:
    respuesta = cliente_cima.get("/api/v1/perfiles/me")

    assert respuesta.status_code == 403
    _assert_cabeceras_api(respuesta)


def test_app_cima_openapi_usa_la_csp_estricta() -> None:
    respuesta = cliente_cima.get("/openapi.json")

    assert respuesta.status_code == 200
    assert respuesta.headers["content-security-policy"] == CSP_API


@pytest.mark.parametrize("ruta", ["/docs", "/redoc"])
def test_app_cima_documentacion_usa_su_csp(ruta: str) -> None:
    respuesta = cliente_cima.get(ruta)

    assert respuesta.status_code == 200
    assert respuesta.headers["content-security-policy"] == CSP_DOCS
    assert respuesta.headers["x-frame-options"] == "DENY"
