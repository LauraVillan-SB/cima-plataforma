"""Pruebas de finalización de microcápsulas, completitud de ruta y eventos de dominio.

Feature: cima-plataforma.
- Property 14: completitud de ruta como bicondicional (Req 4.10).
- Idempotencia de la finalización (Req 4.7).
- Evento `microcapsula_completada` por cápsula y `ruta_completada` al completar la
  ruta, idempotentes y sin que uno descarte al otro (Req 4.6, 8.1, 8.4).

Usan un stub de sesión async que simula el subconjunto del ORM consumido por el
service y por el Metrics Service (get, scalar, add, commit, refresh). El stub
distingue las consultas por tabla y guarda los eventos de métrica por
`client_event_id`, de modo que la idempotencia de Metrics se comporta como en la BD.
"""
from __future__ import annotations

import uuid

import pytest

from app.learning import service
from app.learning.dto import FinalizeRequest
from app.learning.models import LearningPath, PathProgress
from app.metrics.models import MetricEvent


class _ProfileStub:
    """Doble ligero del Perfil: el servicio solo lee `geo_zone` para los eventos."""

    def __init__(self, geo_zone: str) -> None:
        self.geo_zone = geo_zone


class _Session:
    """Sesión async mínima para el flujo de finalización + emisión de eventos.

    - `get(LearningPath, _)` → la ruta; `get(<otro modelo>, _)` → el Perfil (con zona).
    - `scalar(stmt)`: si la consulta es sobre `metric_events` busca el evento por
      `client_event_id` (idempotencia de Metrics); en otro caso devuelve el progreso.
    - `add/commit/refresh` imitan lo que hace la BD: guardan el progreso o el evento
      y asignan la PK tras el commit.
    """

    def __init__(
        self,
        path: LearningPath | None,
        progress: PathProgress | None = None,
        geo_zone: str = "Huila",
    ) -> None:
        self._path = path
        self._progress = progress
        self._profile = _ProfileStub(geo_zone)
        self.events: dict[uuid.UUID, MetricEvent] = {}

    async def get(self, model, _pk):  # noqa: ANN001, ANN201
        if model is LearningPath:
            return self._path
        return self._profile

    async def scalar(self, stmt):  # noqa: ANN001, ANN201
        if "metric_events" in str(stmt):
            client_event_id = next(iter(stmt.compile().params.values()))
            return self.events.get(client_event_id)
        return self._progress

    def add(self, obj) -> None:  # noqa: ANN001
        if isinstance(obj, PathProgress):
            self._progress = obj
        elif isinstance(obj, MetricEvent):
            self.events[obj.client_event_id] = obj

    async def commit(self) -> None:
        return None

    async def refresh(self, obj) -> None:  # noqa: ANN001
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()

    def events_of(self, event_type: str) -> list[MetricEvent]:
        return [e for e in self.events.values() if e.event_type == event_type]


def _path(*capsule_ids: uuid.UUID) -> LearningPath:
    return LearningPath(id=uuid.uuid4(), microcapsule_ids=list(capsule_ids), pass_threshold=70)


def _progress(
    user: uuid.UUID, path: LearningPath, done: list[uuid.UUID], completed: bool = False
) -> PathProgress:
    return PathProgress(
        id=uuid.uuid4(),
        profile_id=user,
        path_id=path.id,
        completed_microcapsules=list(done),
        completed=completed,
        last_completed_step=len(done),
    )


async def _finalize(
    session: _Session,
    user: uuid.UUID,
    capsule: uuid.UUID,
    path: LearningPath,
    client_event_id: uuid.UUID | None = None,
):  # noqa: ANN201
    request = FinalizeRequest(client_event_id=client_event_id or uuid.uuid4(), path_id=path.id)
    return await service.finalize_microcapsule(session, user, capsule, request)


# --------------------------------------------------------------------------- #
# Property 14 — Completitud de ruta como bicondicional (Req 4.10)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_property_14_ruta_no_completa_hasta_finalizar_todas() -> None:
    """La ruta no se marca completada mientras falte alguna microcápsula (Req 4.10)."""
    # Given una ruta de 2 microcápsulas y un Usuario sin progreso previo
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    session = _Session(path)

    # When finaliza solo la primera
    resp = await _finalize(session, user, c1, path)

    # Then la ruta aún no está completa (falta c2) y no se emitió el evento de ruta
    assert resp.path_completed is False
    assert resp.completed_count == 1
    assert resp.total_count == 2
    assert session.events_of("ruta_completada") == []


@pytest.mark.asyncio
async def test_property_14_ruta_completa_al_finalizar_todas() -> None:
    """La ruta se marca completada sii todas las microcápsulas finalizan (Req 4.10)."""
    # Given una ruta de 2 microcápsulas con la primera ya finalizada
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    session = _Session(path, _progress(user, path, [c1]))

    # When finaliza la segunda
    resp = await _finalize(session, user, c2, path)

    # Then la ruta queda completa (bicondicional satisfecho)
    assert resp.path_completed is True
    assert resp.completed_count == 2
    assert resp.total_count == 2


@pytest.mark.asyncio
async def test_finalizacion_es_idempotente() -> None:
    """Finalizar dos veces la misma microcápsula no la cuenta por duplicado (Req 4.7)."""
    # Given una ruta de 2 y un progreso donde c1 ya está finalizada
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    session = _Session(path, _progress(user, path, [c1]))

    # When se vuelve a finalizar c1
    resp = await _finalize(session, user, c1, path)

    # Then el conteo sigue en 1 (sin duplicar) y la ruta no está completa
    assert resp.completed_count == 1
    assert resp.path_completed is False


@pytest.mark.asyncio
async def test_estado_de_ruta_sin_senales_no_adapta() -> None:
    """Sin progreso previo, el estado se entrega estándar (sin adaptación, Req 17.5)."""
    # Given una ruta de 2 microcápsulas y un Usuario sin progreso
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    session = _Session(path)

    # When se consulta el estado de la ruta
    status = await service.get_path_status(session, user, path.id)

    # Then no hay adaptación y el siguiente paso es la primera microcápsula
    assert status.adapted is False
    assert status.completed is False
    assert status.next_microcapsule_id == c1


# --------------------------------------------------------------------------- #
# Evento `microcapsula_completada` por cápsula (Req 4.6, 8.1)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_cada_microcapsula_emite_su_evento_con_la_zona_del_perfil() -> None:
    """Al finalizar una cápsula se registra `microcapsula_completada` con la zona."""
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    session = _Session(path, geo_zone="Huila")

    await _finalize(session, user, c1, path)

    eventos = session.events_of("microcapsula_completada")
    assert len(eventos) == 1
    assert eventos[0].profile_id == user
    assert eventos[0].geo_zone == "Huila"


@pytest.mark.asyncio
async def test_repetir_la_misma_capsula_no_duplica_el_evento() -> None:
    """Repetir una cápsula (aun con otro `client_event_id`) cuenta una sola vez."""
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    session = _Session(path)

    await _finalize(session, user, c1, path, client_event_id=uuid.uuid4())
    await _finalize(session, user, c1, path, client_event_id=uuid.uuid4())

    assert len(session.events_of("microcapsula_completada")) == 1


@pytest.mark.asyncio
async def test_reintento_recupera_el_evento_si_la_emision_fallo_tras_guardar() -> None:
    """Si el progreso quedó guardado pero el evento no se emitió, el reintento lo registra."""
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    # Estado tras un fallo: c1 ya figura finalizada pero no existe el evento (Req 4.7).
    session = _Session(path, _progress(user, path, [c1]))
    assert session.events_of("microcapsula_completada") == []

    await _finalize(session, user, c1, path)

    assert len(session.events_of("microcapsula_completada")) == 1


@pytest.mark.asyncio
async def test_cada_capsula_distinta_cuenta_su_propio_evento() -> None:
    """Dos cápsulas distintas generan dos eventos distintos."""
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    session = _Session(path)

    await _finalize(session, user, c1, path)
    await _finalize(session, user, c2, path)

    assert len(session.events_of("microcapsula_completada")) == 2


def test_clave_del_evento_es_determinista_y_distinta_por_usuario_y_capsula() -> None:
    """La clave de idempotencia depende solo de (Usuario, cápsula)."""
    u1, u2, c1, c2 = (uuid.uuid4() for _ in range(4))

    assert service._microcapsule_event_id(u1, c1) == service._microcapsule_event_id(u1, c1)
    assert service._microcapsule_event_id(u1, c1) != service._microcapsule_event_id(u2, c1)
    assert service._microcapsule_event_id(u1, c1) != service._microcapsule_event_id(u1, c2)


# --------------------------------------------------------------------------- #
# Evento `ruta_completada` al completar la ruta (Req 4.6, 8.1)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_completitud_emite_evento_ruta_completada() -> None:
    """Al completar la ruta se registra un evento `ruta_completada` (Req 4.6, 8.1)."""
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    session = _Session(path, _progress(user, path, [c1]), geo_zone="Huila")

    resp = await _finalize(session, user, c2, path)

    assert resp.path_completed is True
    rutas = session.events_of("ruta_completada")
    assert len(rutas) == 1
    assert rutas[0].profile_id == user
    assert rutas[0].geo_zone == "Huila"


@pytest.mark.asyncio
async def test_ultima_capsula_registra_ambos_eventos_sin_que_uno_descarte_al_otro() -> None:
    """La última cápsula emite el evento de cápsula Y el de ruta, con claves distintas."""
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    session = _Session(path, _progress(user, path, [c1]))
    client_event_id = uuid.uuid4()

    await _finalize(session, user, c2, path, client_event_id=client_event_id)

    # Metrics deduplica por `client_event_id`: si las claves coincidieran, uno de los
    # dos eventos se perdería. Deben existir ambos, y el de ruta conserva la clave
    # de la petición.
    assert len(session.events_of("microcapsula_completada")) == 1
    assert len(session.events_of("ruta_completada")) == 1
    assert client_event_id in session.events
    assert session.events[client_event_id].event_type == "ruta_completada"


@pytest.mark.asyncio
async def test_completitud_no_reemite_ruta_si_ya_estaba_completa() -> None:
    """Re-finalizar una ruta ya completa no vuelve a emitir `ruta_completada`."""
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    # La ruta ya está completa de antes.
    session = _Session(path, _progress(user, path, [c1, c2], completed=True))

    resp = await _finalize(session, user, c1, path)

    # Sigue completa pero no hubo transición: no se emitió un nuevo evento de ruta.
    assert resp.path_completed is True
    assert session.events_of("ruta_completada") == []
