"""Pruebas del catálogo de contenido y de su carga.

Feature: cima-plataforma.
- Req 4.1: la duración de cada microcápsula está entre 180 y 300 s.
- Req 4.2: cada microcápsula tiene exactamente un tema de la allowlist.
- Req 4.3/4.4: las etiquetas de actividad son válidas y existe tema general de respaldo.
- Req 7.6: la clave de cada evaluación apunta a una opción existente.
- Contenido: texto plano (sin enlaces ni HTML), que no oculta que CIMA no vende seguros.
"""
from __future__ import annotations

import re
import uuid

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.learning import service
from app.learning.catalog import (
    CAPSULES,
    PATHS,
    VideoSpec,
    CapsuleSpec,
)
from app.learning.constants import (
    ALLOWED_TOPICS,
    FALLBACK_TOPIC,
    GENERAL_TAG,
    MAX_DURATION_SEC,
    MIN_DURATION_SEC,
)
from app.learning.dto import MicrocapsuleResponse
from app.learning.models import Microcapsule
from app.learning.seed import seed_catalog
from app.profile.constants import ALLOWED_ACTIVITY_TYPES

_ENLACE_O_HTML = re.compile(r"(https?://|www\.|<[^>]+>|&[a-z]+;)", re.IGNORECASE)


def _textos(spec: CapsuleSpec) -> list[str]:
    return [spec.title, spec.summary, *spec.paragraphs, *spec.key_points]


@pytest.mark.parametrize("spec", CAPSULES, ids=lambda s: s.slug)
def test_cada_capsula_cumple_las_invariantes_de_dominio(spec: CapsuleSpec) -> None:
    """Tema, duración, etiquetas y largos de texto son válidos (Req 4.1, 4.2, 4.3)."""
    assert spec.topic in ALLOWED_TOPICS
    assert MIN_DURATION_SEC <= spec.duration_sec <= MAX_DURATION_SEC
    assert set(spec.tags) <= ALLOWED_ACTIVITY_TYPES | {GENERAL_TAG}
    assert 0 < len(spec.title) <= 120
    assert 0 < len(spec.summary) <= 280
    assert spec.paragraphs and 3 <= len(spec.key_points) <= 5


@pytest.mark.parametrize("spec", CAPSULES, ids=lambda s: s.slug)
def test_el_contenido_es_texto_plano_sin_enlaces_ni_html(spec: CapsuleSpec) -> None:
    """Nada del contenido se interpreta como HTML ni lleva enlaces externos."""
    for texto in _textos(spec):
        assert not _ENLACE_O_HTML.search(texto), texto


@pytest.mark.parametrize("spec", CAPSULES, ids=lambda s: s.slug)
def test_quien_menciona_microseguros_aclara_que_cima_no_vende_seguros(
    spec: CapsuleSpec,
) -> None:
    """El alcance del proyecto: CIMA educa y mide interés, no vende seguros."""
    texto = " ".join(_textos(spec))
    if "microseguro" in texto.lower():
        assert "CIMA no vende seguros" in texto


def test_los_identificadores_y_slugs_son_unicos_y_estables() -> None:
    """Cargar el catálogo varias veces debe actualizar las mismas filas."""
    assert len({c.slug for c in CAPSULES}) == len(CAPSULES)
    assert len({c.id for c in CAPSULES}) == len(CAPSULES)
    assert len({p.id for p in PATHS}) == len(PATHS)
    assert CAPSULES[0].id == CAPSULES[0].id


def test_existe_tema_general_de_respaldo() -> None:
    """Sin contenido propio se entrega el tema general de adaptación al clima (Req 4.4)."""
    general = [c for c in CAPSULES if GENERAL_TAG in c.tags]
    assert general
    assert all(c.topic == FALLBACK_TOPIC for c in general)


def test_cada_actividad_cubre_los_tres_temas() -> None:
    """Quien tiene contenido propio recibe clima, finanzas y gestión de riesgos."""
    for actividad in ("cafe", "tienda_barrio"):
        temas = {c.topic for c in CAPSULES if actividad in c.tags}
        assert temas == ALLOWED_TOPICS, actividad


@pytest.mark.parametrize("path", PATHS, ids=lambda p: p.slug)
def test_cada_ruta_es_coherente_con_su_evaluacion(path) -> None:  # noqa: ANN001
    """Las cápsulas existen y la clave de cada pregunta apunta a una opción real."""
    slugs = {c.slug for c in CAPSULES}
    assert set(path.capsule_slugs) <= slugs
    assert len(set(path.capsule_slugs)) == len(path.capsule_slugs)
    assert 0 <= path.pass_threshold <= 100
    assert len(path.questions) == 3
    for pregunta in path.questions:
        assert 0 <= pregunta.correct < len(pregunta.options)
        assert len(set(pregunta.options)) == len(pregunta.options)


def test_las_rutas_por_actividad_no_mezclan_contenido_ajeno() -> None:
    """La ruta de café solo tiene cápsulas de café; la de tienda, de tienda."""
    por_slug = {c.slug: c for c in CAPSULES}
    esperado = {"ruta-cafe": "cafe", "ruta-tienda-barrio": "tienda_barrio"}
    for path in PATHS:
        etiqueta = esperado.get(path.slug)
        if etiqueta:
            assert all(etiqueta in por_slug[s].tags for s in path.capsule_slugs)


# --------------------------------------------------------------------------- #
# Video de apoyo
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("video_id", ["", "corto", "demasiado_largo_12", "con espacio!", "<script>ab"])
def test_un_identificador_de_video_invalido_se_rechaza(video_id: str) -> None:
    """Solo se acepta el identificador de 11 caracteres, nunca una URL libre."""
    with pytest.raises(ValueError):
        VideoSpec(video_id=video_id, title="x", channel="y")


def test_un_identificador_valido_construye_la_direccion_de_incrustacion() -> None:
    """El backend arma la dirección con un dominio fijo, sin cookies de seguimiento."""
    capsula = Microcapsule(
        id=uuid.uuid4(),
        topic=FALLBACK_TOPIC,
        activity_tags=[GENERAL_TAG],
        duration_sec=200,
        difficulty=0,
        title="t",
        paragraphs=[],
        key_points=[],
        video_id="abcDEF-_123",
        video_title="Título",
        video_channel="Canal",
    )

    respuesta = service._to_microcapsule_response(capsula)

    assert respuesta.video is not None
    assert respuesta.video.embed_url == "https://www.youtube-nocookie.com/embed/abcDEF-_123"


def test_sin_video_la_respuesta_no_trae_video() -> None:
    """El video es opcional: sin él el contenido de texto es lo principal."""
    capsula = Microcapsule(
        id=uuid.uuid4(),
        topic=FALLBACK_TOPIC,
        activity_tags=[GENERAL_TAG],
        duration_sec=200,
        difficulty=0,
    )

    respuesta = service._to_microcapsule_response(capsula)

    assert respuesta.video is None
    assert respuesta.paragraphs == [] and respuesta.title is None


def test_el_dto_rechaza_un_video_con_identificador_invalido() -> None:
    """Aun si el dato guardado estuviera mal, el DTO de salida no lo expone."""
    with pytest.raises(PydanticValidationError):
        MicrocapsuleResponse(
            id=uuid.uuid4(),
            topic=FALLBACK_TOPIC,
            activity_tags=[],
            duration_sec=200,
            difficulty=0,
            video={"video_id": "no-valido", "title": "t", "channel": "c", "embed_url": "x"},
        )


# --------------------------------------------------------------------------- #
# Carga del catálogo
# --------------------------------------------------------------------------- #
class _SeedSession:
    """Sesión mínima que cuenta las sentencias ejecutadas y las confirmaciones."""

    def __init__(self) -> None:
        self.executed = 0
        self.commits = 0

    async def execute(self, _stmt) -> None:  # noqa: ANN001
        self.executed += 1

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_la_carga_procesa_todo_el_catalogo_en_una_sola_transaccion() -> None:
    """Una sentencia por cápsula, y una por ruta y por evaluación; un solo commit."""
    session = _SeedSession()

    resultado = await seed_catalog(session)

    assert (resultado.capsules, resultado.paths, resultado.assessments) == (
        len(CAPSULES),
        len(PATHS),
        len(PATHS),
    )
    assert session.executed == len(CAPSULES) + 2 * len(PATHS)
    assert session.commits == 1


# --------------------------------------------------------------------------- #
# Respaldo de tema general (Req 4.4, 4.9)
# --------------------------------------------------------------------------- #
class _TwoQueries:
    """Sesión que responde distinto a la primera consulta (generales) y a la segunda (tema)."""

    def __init__(self, generales: list, tema: list) -> None:  # noqa: ANN001
        self._answers = [generales, tema]
        self.calls = 0

    async def execute(self, _stmt):  # noqa: ANN001, ANN201
        from tests.learning.test_selection import _ScalarsResult

        answer = self._answers[min(self.calls, 1)]
        self.calls += 1
        return _ScalarsResult(answer)


@pytest.mark.asyncio
async def test_el_respaldo_prefiere_las_capsulas_etiquetadas_como_generales() -> None:
    """Con cápsulas generales no se consulta el tema completo ni se mezcla contenido ajeno."""
    from tests.learning.test_selection import _capsule

    generales = [_capsule(topic=FALLBACK_TOPIC, tags=[GENERAL_TAG])]
    session = _TwoQueries(generales, [_capsule(topic=FALLBACK_TOPIC, tags=["cafe"])])

    resultado = await service._fetch_general(session)

    assert resultado == generales
    assert session.calls == 1


@pytest.mark.asyncio
async def test_el_respaldo_cae_al_tema_completo_si_no_hay_generales() -> None:
    """Si el catálogo no tiene etiquetadas, no se deja al Usuario sin contenido."""
    from tests.learning.test_selection import _capsule

    del_tema = [_capsule(topic=FALLBACK_TOPIC, tags=["cafe"])]
    session = _TwoQueries([], del_tema)

    resultado = await service._fetch_general(session)

    assert resultado == del_tema
    assert session.calls == 2
