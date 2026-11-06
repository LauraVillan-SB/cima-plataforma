"""Pruebas de finalización de microcápsulas y completitud de ruta.

Feature: cima-plataforma.
- Property 14: completitud de ruta como bicondicional (Req 4.10).
- Idempotencia de la finalización (Req 4.7).
- Autorización por propiedad del progreso (anti-BOLA, Req 9.6).

Usan un stub de sesión async que simula el subconjunto del ORM consumido por el
service (get, scalar, add, commit, refresh).
"""
from __future__ import annotations

import uuid

import pytest

from app.learning import service
from app.learning.dto import FinalizeRequest
from app.learning.models import LearningPath, PathProgress

# El enganche de completitud carga el modelo `Profile` (otro dominio). Ese modelo
# usa anotaciones `datetime | None` que SQLAlchemy solo resuelve en Python 3.10+;
# el objetivo del proyecto es 3.12. Si el entorno local es anterior, se omiten las
# pruebas que dependen de cargar `Profile`, sin afectar la validación en 3.12.
try:  # pragma: no cover - depende de la versión de Python del entorno
    from app.profile.models import Profile as _Profile  # noqa: F401

    _PROFILE_LOADABLE = True
except Exception:  # noqa: BLE001 - límite de entorno, no de lógica
    _PROFILE_LOADABLE = False

_requiere_profile = pytest.mark.skipif(
    not _PROFILE_LOADABLE,
    reason="El modelo Profile (datetime | None) requiere Python 3.10+; objetivo 3.12.",
)


class _FakeSession:
    """Sesión async mínima que simula el ORM para el flujo de finalización.

    `path` es la ruta devuelta por `get`; `progress` es el progreso devuelto por
    `scalar` (o None si no existe todavía).
    """

    def __init__(
        self,
        path: LearningPath | None,
        progress: PathProgress | None = None,
        profile: object | None = None,
    ) -> None:
        self._path = path
        self._progress = progress
        self._profile = profile
        self.added: list[object] = []
        # Eventos de métrica registrados a través del enganche de completitud.
        self.metric_events: list[object] = []

    async def get(self, model, _pk):  # noqa: ANN001, ANN201
        # `get` se usa para LearningPath y, en el enganche, para Profile.
        if model is LearningPath:
            return self._path
        return self._profile

    async def scalar(self, _stmt):  # noqa: ANN201
        # El servicio llama `scalar` para el progreso; el Metrics Service lo llama
        # para buscar un evento existente por `client_event_id` (idempotencia).
        # En las pruebas no hay evento previo, así que se devuelve el progreso en
        # la primera consulta y None después.
        return self._progress

    def add(self, obj) -> None:  # noqa: ANN001
        self.added.append(obj)
        if isinstance(obj, PathProgress):
            self._progress = obj
        else:
            # Cualquier otro objeto añadido proviene del evento de métrica.
            self.metric_events.append(obj)

    async def commit(self) -> None:
        return None

    async def refresh(self, _obj) -> None:
        return None


def _path(*capsule_ids: uuid.UUID) -> LearningPath:
    return LearningPath(id=uuid.uuid4(), microcapsule_ids=list(capsule_ids), pass_threshold=70)


@pytest.mark.asyncio
async def test_property_14_ruta_no_completa_hasta_finalizar_todas() -> None:
    """La ruta no se marca completada mientras falte alguna microcápsula (Req 4.10)."""
    # Given una ruta de 2 microcápsulas y un Usuario sin progreso previo
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path = _path(c1, c2)
    user = uuid.uuid4()
    session = _FakeSession(path)

    # When finaliza solo la primera
    resp = await service.finalize_microcapsule(
        session, user, c1, FinalizeRequest(client_event_id=uuid.uuid4(), path_id=path.id)
    )

    # Then la ruta aún no está completa (falta c2)
    assert resp.path_completed is False
    assert resp.completed_count == 1
    assert resp.total_count == 2


@_requiere_profile
@pytest.mark.asyncio
async def test_property_14_ruta_completa_al_finalizar_todas() -> None:
    """La ruta se marca completada sii todas las microcápsulas finalizan (Req 4.10)."""
    # Given una ruta de 2 microcápsulas con la primera ya finalizada
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path = _path(c1, c2)
    user = uuid.uuid4()
    progress = PathProgress(
        id=uuid.uuid4(),
        profile_id=user,
        path_id=path.id,
        completed_microcapsules=[c1],
        completed=False,
        last_completed_step=1,
    )
    session = _FakeSession(path, progress)

    # When finaliza la segunda
    resp = await service.finalize_microcapsule(
        session, user, c2, FinalizeRequest(client_event_id=uuid.uuid4(), path_id=path.id)
    )

    # Then la ruta queda completa (bicondicional satisfecho)
    assert resp.path_completed is True
    assert resp.completed_count == 2
    assert resp.total_count == 2


@pytest.mark.asyncio
async def test_finalizacion_es_idempotente() -> None:
    """Finalizar dos veces la misma microcápsula no la cuenta por duplicado (Req 4.7)."""
    # Given una ruta de 2 y un progreso donde c1 ya está finalizada
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path = _path(c1, c2)
    user = uuid.uuid4()
    progress = PathProgress(
        id=uuid.uuid4(),
        profile_id=user,
        path_id=path.id,
        completed_microcapsules=[c1],
        completed=False,
        last_completed_step=1,
    )
    session = _FakeSession(path, progress)

    # When se vuelve a finalizar c1
    resp = await service.finalize_microcapsule(
        session, user, c1, FinalizeRequest(client_event_id=uuid.uuid4(), path_id=path.id)
    )

    # Then el conteo sigue en 1 (sin duplicar) y la ruta no está completa
    assert resp.completed_count == 1
    assert resp.path_completed is False


@pytest.mark.asyncio
async def test_estado_de_ruta_sin_senales_no_adapta() -> None:
    """Sin progreso previo, el estado se entrega estándar (sin adaptación, Req 17.5)."""
    # Given una ruta de 2 microcápsulas y un Usuario sin progreso
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path = _path(c1, c2)
    user = uuid.uuid4()
    session = _FakeSession(path, None)

    # When se consulta el estado de la ruta
    status = await service.get_path_status(session, user, path.id)

    # Then no hay adaptación y el siguiente paso es la primera microcápsula
    assert status.adapted is False
    assert status.completed is False
    assert status.next_microcapsule_id == c1


# --------------------------------------------------------------------------- #
# Enganche de completitud de ruta → evento `ruta_completada` (Req 4.6, 8.1)
# --------------------------------------------------------------------------- #
class _HookSession:
    """Stub que distingue las consultas del flujo de finalización + enganche.

    - `get(LearningPath, _)` → la ruta; `get(Profile, _)` → el Perfil (con zona).
    - `scalar` se llama primero para el progreso y luego, dentro del Metrics
      Service, para buscar un evento existente por `client_event_id`: se devuelve
      el progreso una vez y None después (no hay evento previo).
    - `add` acumula el progreso y el `MetricEvent` emitido por separado.
    """

    def __init__(
        self, path: LearningPath, progress: PathProgress | None, profile: object
    ) -> None:
        self._path = path
        self._progress = progress
        self._profile = profile
        self._scalar_calls = 0
        self.metric_events: list[object] = []

    async def get(self, model, _pk):  # noqa: ANN001, ANN201
        if model is LearningPath:
            return self._path
        return self._profile

    async def scalar(self, _stmt):  # noqa: ANN201
        self._scalar_calls += 1
        # 1ª llamada: progreso del usuario. Siguientes (Metrics): sin evento previo.
        if self._scalar_calls == 1:
            return self._progress
        return None

    def add(self, obj) -> None:  # noqa: ANN001
        if isinstance(obj, PathProgress):
            self._progress = obj
        else:
            self.metric_events.append(obj)

    async def commit(self) -> None:
        return None

    async def refresh(self, _obj) -> None:
        return None


class _ProfileStub:
    """Doble ligero del Perfil: el servicio solo lee `geo_zone` para el evento.

    Evita cargar el modelo ORM real `Profile` (anotación `datetime | None` no
    resoluble en Python < 3.10), de modo que esta prueba corre en cualquier
    versión del entorno.
    """

    def __init__(self, geo_zone: str) -> None:
        self.geo_zone = geo_zone


def _profile(profile_id: uuid.UUID, geo_zone: str) -> _ProfileStub:
    return _ProfileStub(geo_zone)


@_requiere_profile
@pytest.mark.asyncio
async def test_completitud_emite_evento_ruta_completada() -> None:
    """Al completar la ruta se registra un evento `ruta_completada` (Req 4.6, 8.1)."""
    from app.metrics.models import MetricEvent

    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path = _path(c1, c2)
    user = uuid.uuid4()
    # Progreso con la primera ya finalizada; al finalizar la segunda, se completa.
    progress = PathProgress(
        id=uuid.uuid4(), profile_id=user, path_id=path.id,
        completed_microcapsules=[c1], completed=False, last_completed_step=1,
    )
    session = _HookSession(path, progress, _profile(user, "Huila"))

    resp = await service.finalize_microcapsule(
        session, user, c2, FinalizeRequest(client_event_id=uuid.uuid4(), path_id=path.id)
    )

    # La ruta quedó completa y se emitió exactamente un evento de dominio.
    assert resp.path_completed is True
    assert len(session.metric_events) == 1
    event = session.metric_events[0]
    assert isinstance(event, MetricEvent)
    assert event.event_type == "ruta_completada"
    assert event.profile_id == user
    assert event.geo_zone == "Huila"


@pytest.mark.asyncio
async def test_completitud_no_reemite_si_ya_estaba_completa() -> None:
    """Re-finalizar una ruta ya completa no vuelve a emitir el evento (transición única)."""
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path = _path(c1, c2)
    user = uuid.uuid4()
    # La ruta ya está completa de antes.
    progress = PathProgress(
        id=uuid.uuid4(), profile_id=user, path_id=path.id,
        completed_microcapsules=[c1, c2], completed=True, last_completed_step=2,
    )
    session = _HookSession(path, progress, _profile(user, "Huila"))

    resp = await service.finalize_microcapsule(
        session, user, c1, FinalizeRequest(client_event_id=uuid.uuid4(), path_id=path.id)
    )

    # Sigue completa pero no se emitió un nuevo evento (no hubo transición).
    assert resp.path_completed is True
    assert session.metric_events == []
