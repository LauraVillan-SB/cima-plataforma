"""Pruebas del listado de rutas con el avance del Usuario (`GET /aprendizaje/rutas`).

Verifican qué rutas ve cada Usuario según su actividad, el estado de cada cápsula
(completada, siguiente, pendiente) y el avance. Las consultas se sustituyen por dobles
en memoria; que solo se lea el progreso del titular y que las rutas sin título no se
publiquen se verifica contra Postgres real.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.learning import service
from app.learning.constants import FALLBACK_TOPIC, GENERAL_TAG
from app.learning.models import LearningPath, Microcapsule, PathProgress


def _capsule(tags: list[str], title: str = "Cápsula") -> Microcapsule:
    return Microcapsule(
        id=uuid.uuid4(),
        topic=FALLBACK_TOPIC,
        activity_tags=tags,
        duration_sec=200,
        difficulty=0,
        title=title,
        paragraphs=["Texto."],
        key_points=["Punto."],
    )


def _route(title: str, capsules: list[Microcapsule]) -> LearningPath:
    return LearningPath(
        id=uuid.uuid4(),
        microcapsule_ids=[c.id for c in capsules],
        pass_threshold=70,
        title=title,
        summary="Resumen.",
    )


def _progress(user: uuid.UUID, path: LearningPath, done: list[Microcapsule]) -> PathProgress:
    return PathProgress(
        id=uuid.uuid4(),
        profile_id=user,
        path_id=path.id,
        completed_microcapsules=[c.id for c in done],
        completed=len(done) == len(path.microcapsule_ids),
        last_completed_step=len(done),
    )


class _Db:
    """Sesión mínima: solo `get(Profile, id)` devuelve el Perfil con su actividad."""

    def __init__(self, activity: str | None) -> None:
        self._profile = SimpleNamespace(activity_type=activity)

    async def get(self, _model, _pk):  # noqa: ANN001, ANN201
        return self._profile


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    paths: list[LearningPath],
    capsules: list[Microcapsule],
    progress: dict[uuid.UUID, PathProgress] | None = None,
    passed: set[uuid.UUID] | None = None,
) -> None:
    async def _paths(_db):  # noqa: ANN001, ANN202
        return paths

    async def _caps(_db, _ids):  # noqa: ANN001, ANN202
        return {c.id: c for c in capsules}

    async def _prog(_db, _user):  # noqa: ANN001, ANN202
        return progress or {}

    async def _passed(_db, _user):  # noqa: ANN001, ANN202
        return passed or set()

    monkeypatch.setattr(service, "_fetch_paths", _paths)
    monkeypatch.setattr(service, "_fetch_capsules_by_id", _caps)
    monkeypatch.setattr(service, "_fetch_progress_by_path", _prog)
    monkeypatch.setattr(service, "_fetch_passed_paths", _passed)


def _catalog() -> tuple[list[LearningPath], list[Microcapsule], dict[str, LearningPath]]:
    cafe = [_capsule(["cafe"], f"Café {i}") for i in range(3)]
    tienda = [_capsule(["tienda_barrio"], f"Tienda {i}") for i in range(3)]
    general = [_capsule([GENERAL_TAG], f"General {i}") for i in range(3)]
    rutas = {
        "cafe": _route("Ruta del cafetal", cafe),
        "tienda": _route("Ruta de la tienda", tienda),
        "general": _route("Ruta general", general),
    }
    return list(rutas.values()), cafe + tienda + general, rutas


@pytest.mark.asyncio
async def test_quien_cultiva_cafe_ve_su_ruta_primero_y_luego_la_general(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Se listan la ruta de su actividad y la general; la de otra actividad no."""
    paths, capsules, _ = _catalog()
    _patch(monkeypatch, paths, capsules)

    respuesta = await service.list_routes(_Db("cafe"), uuid.uuid4())

    assert [r.title for r in respuesta.routes] == ["Ruta del cafetal", "Ruta general"]


@pytest.mark.asyncio
async def test_quien_no_tiene_actividad_solo_ve_la_ruta_general(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin actividad no se le muestra contenido de un cultivo o comercio ajeno."""
    paths, capsules, _ = _catalog()
    _patch(monkeypatch, paths, capsules)

    for actividad in (None, "", "   "):
        respuesta = await service.list_routes(_Db(actividad), uuid.uuid4())
        assert [r.title for r in respuesta.routes] == ["Ruta general"]


@pytest.mark.asyncio
async def test_el_estado_de_cada_capsula_refleja_el_avance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Completada la primera: la segunda es la siguiente y la tercera queda pendiente."""
    paths, capsules, rutas = _catalog()
    usuario = uuid.uuid4()
    ruta = rutas["cafe"]
    avance = _progress(usuario, ruta, [capsules[0]])
    _patch(monkeypatch, paths, capsules, progress={ruta.id: avance})

    respuesta = await service.list_routes(_Db("cafe"), usuario)

    cafe = respuesta.routes[0]
    assert [i.status for i in cafe.items] == ["completed", "next", "pending"]
    assert [i.position for i in cafe.items] == [1, 2, 3]
    assert (cafe.completed_count, cafe.total_count, cafe.completed) == (1, 3, False)
    assert cafe.next_microcapsule_id == cafe.items[1].capsule.id


@pytest.mark.asyncio
async def test_una_ruta_terminada_no_tiene_siguiente_y_marca_la_evaluacion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con todas finalizadas la ruta está completa; `assessment_passed` viene de los intentos."""
    paths, capsules, rutas = _catalog()
    usuario = uuid.uuid4()
    ruta = rutas["cafe"]
    avance = _progress(usuario, ruta, capsules[0:3])
    _patch(monkeypatch, paths, capsules, progress={ruta.id: avance}, passed={ruta.id})

    respuesta = await service.list_routes(_Db("cafe"), usuario)

    cafe = respuesta.routes[0]
    assert cafe.completed is True and cafe.next_microcapsule_id is None
    assert all(i.status == "completed" for i in cafe.items)
    assert cafe.assessment_passed is True
    assert respuesta.routes[1].assessment_passed is False


@pytest.mark.asyncio
async def test_sin_progreso_la_primera_capsula_es_la_siguiente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un Usuario nuevo empieza por la primera cápsula y nada está completado."""
    paths, capsules, _ = _catalog()
    _patch(monkeypatch, paths, capsules)

    respuesta = await service.list_routes(_Db(None), uuid.uuid4())

    general = respuesta.routes[0]
    assert [i.status for i in general.items] == ["next", "pending", "pending"]
    assert general.completed_count == 0 and general.completed is False


@pytest.mark.asyncio
async def test_las_capsulas_que_ya_no_existen_se_omiten(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si una cápsula de la ruta fue borrada, no se lista ni cuenta para el total."""
    paths, capsules, rutas = _catalog()
    faltante = rutas["general"].microcapsule_ids[1]
    _patch(monkeypatch, paths, [c for c in capsules if c.id != faltante])

    respuesta = await service.list_routes(_Db(None), uuid.uuid4())

    assert respuesta.routes[0].total_count == 2


@pytest.mark.asyncio
async def test_la_respuesta_trae_el_contenido_de_cada_capsula(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cada cápsula incluye su contenido para que el cliente no necesite otra llamada."""
    paths, capsules, _ = _catalog()
    _patch(monkeypatch, paths, capsules)

    respuesta = await service.list_routes(_Db(None), uuid.uuid4())

    primera = respuesta.routes[0].items[0].capsule
    assert primera.title == "General 0" and primera.paragraphs == ["Texto."]
    assert respuesta.routes[0].audience_tags == [GENERAL_TAG]


def test_la_relevancia_depende_de_la_actividad_o_de_ser_general() -> None:
    """La ruta es relevante si trae la actividad del Usuario o es general."""
    assert service._is_relevant(["cafe"], "cafe") is True
    assert service._is_relevant(["cafe"], "") is False
    assert service._is_relevant(["tienda_barrio"], "cafe") is False
    assert service._is_relevant([GENERAL_TAG], "") is True
    assert service._is_relevant([GENERAL_TAG], "cafe") is True
