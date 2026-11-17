"""Pruebas del video propio de las microcápsulas y del endpoint que lo sirve.

Feature: cima-plataforma. Seguridad (OWASP A01, path traversal): solo nombres de la
allowlist, la ruta queda dentro de la carpeta de medios y solo con sesión. El video es
un complemento: el contenido principal sigue siendo el texto.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError as PydanticValidationError

from app.common.security import get_current_user_id
from app.learning import media, service
from app.learning.catalog import CAPSULES, CapsuleSpec
from app.learning.constants import FALLBACK_TOPIC, GENERAL_TAG
from app.learning.dto import VideoFileOut
from app.learning.models import Microcapsule
from app.main import app

_CONTENIDO = b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 4


@pytest.fixture()
def carpeta(tmp_path: Path) -> Path:
    """Carpeta de medios temporal con un video de prueba y un archivo ajeno al lado."""
    medios = tmp_path / "media"
    medios.mkdir()
    (medios / "video-prueba.mp4").write_bytes(_CONTENIDO)
    (tmp_path / "secreto.mp4").write_bytes(b"no debe salir")
    return medios


@pytest.fixture()
def cliente(carpeta: Path):
    """App real con sesión simulada y la carpeta temporal como carpeta de medios."""
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    with patch.object(media, "carpeta_medios", return_value=carpeta):
        yield TestClient(app)
    app.dependency_overrides.pop(get_current_user_id, None)


# --------------------------------------------------------------------------- #
# Resolución segura del archivo
# --------------------------------------------------------------------------- #
def test_un_nombre_valido_existente_se_resuelve_dentro_de_la_carpeta(carpeta: Path) -> None:
    ruta = media.resolver_medio("video-prueba.mp4", carpeta)

    assert ruta is not None
    assert ruta.parent == carpeta.resolve()


@pytest.mark.parametrize(
    "nombre",
    [
        "../secreto.mp4",
        "..\\secreto.mp4",
        "/etc/passwd",
        "C:\\Windows\\win.ini",
        "video-prueba.MP4",
        "Video-Prueba.mp4",
        "video prueba.mp4",
        "video_prueba.mp4",
        "video-prueba.mp4.exe",
        "video-prueba",
        ".mp4",
        "-video.mp4",
        "no-existe.mp4",
        "",
    ],
)
def test_un_nombre_fuera_de_la_allowlist_o_inexistente_no_se_resuelve(carpeta: Path, nombre: str) -> None:
    assert media.resolver_medio(nombre, carpeta) is None


@settings(max_examples=200, deadline=None)
@given(nombre=st.text(max_size=80))
def test_nunca_se_resuelve_un_archivo_fuera_de_la_carpeta(tmp_path_factory, nombre: str) -> None:  # noqa: ANN001
    """Para cualquier nombre, o no hay archivo o queda justo dentro de la carpeta."""
    base = tmp_path_factory.mktemp("medios")
    ruta = media.resolver_medio(nombre, base)

    assert ruta is None or ruta.parent == base.resolve()


def test_un_enlace_simbolico_que_apunta_afuera_no_se_sirve(carpeta: Path) -> None:
    enlace = carpeta / "enlace.mp4"
    try:
        enlace.symlink_to(carpeta.parent / "secreto.mp4")
    except OSError:
        pytest.skip("El sistema no permite crear enlaces simbólicos sin permisos.")

    assert media.resolver_medio("enlace.mp4", carpeta) is None


def test_la_url_la_arma_el_backend_con_el_prefijo_fijo() -> None:
    assert media.url_de("agro-riesgos.mp4") == "/api/v1/aprendizaje/medios/agro-riesgos.mp4"
    with pytest.raises(ValueError):
        media.url_de("../otro.mp4")


# --------------------------------------------------------------------------- #
# Endpoint
# --------------------------------------------------------------------------- #
def test_con_sesion_entrega_el_video_completo(cliente: TestClient) -> None:
    respuesta = cliente.get("/api/v1/aprendizaje/medios/video-prueba.mp4")

    assert respuesta.status_code == 200
    assert respuesta.content == _CONTENIDO
    assert respuesta.headers["content-type"] == "video/mp4"
    assert respuesta.headers["cache-control"] == "private, max-age=86400"
    assert respuesta.headers["x-content-type-options"] == "nosniff"


def test_admite_rangos_para_adelantar_sin_bajar_todo(cliente: TestClient) -> None:
    respuesta = cliente.get("/api/v1/aprendizaje/medios/video-prueba.mp4", headers={"Range": "bytes=10-19"})

    assert respuesta.status_code == 206
    assert respuesta.content == _CONTENIDO[10:20]


@pytest.mark.parametrize("nombre", ["no-existe.mp4", "..%2Fsecreto.mp4", "%2E%2E%5Csecreto.mp4", "video_prueba.mp4"])
def test_un_nombre_invalido_responde_404_generico(cliente: TestClient, nombre: str) -> None:
    respuesta = cliente.get(f"/api/v1/aprendizaje/medios/{nombre}")

    assert respuesta.status_code == 404
    assert "secreto" not in respuesta.text
    assert "media" not in respuesta.text.lower()


def test_sin_sesion_no_entrega_el_video(carpeta: Path) -> None:
    with patch.object(media, "carpeta_medios", return_value=carpeta):
        respuesta = TestClient(app).get("/api/v1/aprendizaje/medios/video-prueba.mp4")

    # La app responde 403 a toda ruta protegida sin cookie de sesión (`ForbiddenError`).
    assert respuesta.status_code == 403
    assert respuesta.content != _CONTENIDO


# --------------------------------------------------------------------------- #
# Contrato de la cápsula
# --------------------------------------------------------------------------- #
def _capsula(**kw: object) -> Microcapsule:
    base: dict = {
        "id": uuid.uuid4(),
        "topic": FALLBACK_TOPIC,
        "activity_tags": [GENERAL_TAG],
        "duration_sec": 200,
        "difficulty": 0,
        "title": "Lección",
        "paragraphs": [],
        "key_points": [],
    }
    base.update(kw)
    return Microcapsule(**base)


def test_la_respuesta_trae_la_url_del_video_propio() -> None:
    respuesta = service._to_microcapsule_response(_capsula(video_file="agro-riesgos.mp4"))

    assert respuesta.video_file is not None
    assert respuesta.video_file.url == "/api/v1/aprendizaje/medios/agro-riesgos.mp4"
    assert respuesta.video_file.title == "Lección"


@pytest.mark.parametrize("guardado", [None, "", "../x.mp4", "https://otro.com/x.mp4"])
def test_sin_video_propio_valido_la_respuesta_no_lo_trae(guardado: str | None) -> None:
    """Aun si el dato guardado estuviera mal, no se expone una dirección armada con él."""
    assert service._to_microcapsule_response(_capsula(video_file=guardado)).video_file is None


@pytest.mark.parametrize("url", ["https://otro.com/x.mp4", "/api/v1/aprendizaje/medios/../x.mp4", "javascript:alert(1)"])
def test_el_dto_rechaza_una_url_que_no_es_del_backend(url: str) -> None:
    with pytest.raises(PydanticValidationError):
        VideoFileOut(url=url, title="t")


def test_el_catalogo_rechaza_un_nombre_de_video_invalido() -> None:
    with pytest.raises(ValueError):
        CapsuleSpec(
            slug="x",
            topic=FALLBACK_TOPIC,
            tags=(GENERAL_TAG,),
            relevance=1.0,
            title="t",
            summary="s",
            paragraphs=("p",),
            key_points=("k",),
            video_file="../fuera.mp4",
        )


def test_las_capsulas_con_video_propio_usan_nombres_de_la_allowlist() -> None:
    con_video = [c for c in CAPSULES if c.video_file]

    assert {c.video_file for c in con_video} == {"agro-sostenible.mp4", "agro-riesgos.mp4", "tienda-videos.mp4"}
    assert all(media.nombre_valido(c.video_file) for c in con_video)
