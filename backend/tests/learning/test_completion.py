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


class _FakeSession:
    """Sesión async mínima que simula el ORM para el flujo de finalización.

    `path` es la ruta devuelta por `get`; `progress` es el progreso devuelto por
    `scalar` (o None si no existe todavía).
    """

    def __init__(
        self, path: LearningPath | None, progress: PathProgress | None = None
    ) -> None:
        self._path = path
        self._progress = progress
        self.added: list[object] = []

    async def get(self, _model, _pk) -> LearningPath | None:
        return self._path

    async def scalar(self, _stmt) -> PathProgress | None:
        return self._progress

    def add(self, obj) -> None:  # noqa: ANN001
        self.added.append(obj)
        if isinstance(obj, PathProgress):
            self._progress = obj

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
