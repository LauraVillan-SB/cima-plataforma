"""Pruebas de propiedad del Offline Sync Service.

Feature: cima-plataforma
- Property 36: Idempotencia de la sincronización offline (Tarea 20.2, Req 18.2).
- Property 37: Fusión monótona de progreso sin pérdida (Tarea 20.3, Req 18.4).

El stub de sesión resuelve los `scalar` del servicio inspeccionando la tabla
referida por la sentencia (`sync_actions` para la idempotencia por
`client_event_id`, `sync_path_progress` para el progreso por (perfil, ruta)) y
mantiene el estado en memoria. No hay BD real.
"""
from __future__ import annotations

import uuid

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.sync import service
from app.sync.dto import SyncAction, SyncBatchRequest
from app.sync.models import SyncAction as SyncActionModel
from app.sync.models import SyncPathProgress


class _FakeSession:
    """Sesión async que imita el almacén de `sync_actions` y `sync_path_progress`."""

    def __init__(self) -> None:
        self.actions: list[SyncActionModel] = []
        self.progress: list[SyncPathProgress] = []
        self.commits = 0

    async def scalar(self, stmt):
        texto = str(stmt)
        if "sync_actions" in texto:
            event_id = _bind_value(stmt, "client_event_id")
            found = next(
                (a for a in self.actions if str(a.client_event_id) == str(event_id)),
                None,
            )
            return found.id if found else None
        # sync_path_progress
        profile_id = _bind_value(stmt, "profile_id")
        path_id = _bind_value(stmt, "path_id")
        return next(
            (
                p
                for p in self.progress
                if str(p.profile_id) == str(profile_id)
                and str(p.path_id) == str(path_id)
            ),
            None,
        )

    def add(self, obj) -> None:
        if isinstance(obj, SyncActionModel):
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()
            self.actions.append(obj)
        elif isinstance(obj, SyncPathProgress):
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()
            self.progress.append(obj)

    async def commit(self) -> None:
        self.commits += 1


def _bind_value(stmt, column: str):
    params = stmt.compile().params
    for key, value in params.items():
        if key.startswith(column):
            return value
    return None


def _finalizacion(path_id: uuid.UUID, microcapsule: str) -> SyncAction:
    return SyncAction(
        client_event_id=uuid.uuid4(),
        action_type="microcapsula_finalizada",
        payload={"path_id": str(path_id), "microcapsule_id": microcapsule},
    )


# Feature: cima-plataforma, Property 36: Idempotencia de la sincronización offline.
# Validates: Requirements 18.2
@settings(max_examples=50, deadline=None)
@given(n_pasos=st.integers(min_value=1, max_value=6))
@pytest.mark.asyncio
async def test_property_36_reaplicar_lote_no_duplica(n_pasos: int) -> None:
    """Reaplicar el mismo lote no vuelve a aplicar ninguna acción (idempotente)."""
    user_id = uuid.uuid4()
    path_id = uuid.uuid4()
    acciones = [_finalizacion(path_id, f"mc-{i}") for i in range(n_pasos)]
    batch = SyncBatchRequest(profile_id=user_id, actions=acciones)
    sesion = _FakeSession()

    primera = await service.apply_batch(sesion, user_id, batch)
    segunda = await service.apply_batch(sesion, user_id, batch)

    assert primera.applied_count == n_pasos
    assert primera.duplicate_count == 0
    # La segunda vez: todas duplicadas, ninguna aplicada.
    assert segunda.applied_count == 0
    assert segunda.duplicate_count == n_pasos
    # No se crean registros de acción duplicados.
    assert len(sesion.actions) == n_pasos


# Feature: cima-plataforma, Property 37: Fusión monótona de progreso sin pérdida.
# Validates: Requirements 18.4
@settings(max_examples=50, deadline=None)
@given(
    primeros=st.lists(st.sampled_from(["a", "b", "c", "d"]), min_size=1, max_size=4, unique=True),
    segundos=st.lists(st.sampled_from(["c", "d", "e", "f"]), min_size=1, max_size=4, unique=True),
)
@pytest.mark.asyncio
async def test_property_37_union_monotona_sin_perdida(
    primeros: list[str], segundos: list[str]
) -> None:
    """El progreso tras dos lotes es la unión de ambos, sin perder ningún paso."""
    user_id = uuid.uuid4()
    path_id = uuid.uuid4()
    sesion = _FakeSession()

    batch1 = SyncBatchRequest(
        profile_id=user_id,
        actions=[_finalizacion(path_id, mc) for mc in primeros],
    )
    batch2 = SyncBatchRequest(
        profile_id=user_id,
        actions=[_finalizacion(path_id, mc) for mc in segundos],
    )

    await service.apply_batch(sesion, user_id, batch1)
    await service.apply_batch(sesion, user_id, batch2)

    progreso = next(p for p in sesion.progress if p.path_id == path_id)
    esperado = set(primeros) | set(segundos)
    assert set(progreso.completed_microcapsules) == esperado
    # Sin duplicados y en orden estable (determinista).
    assert progreso.completed_microcapsules == sorted(esperado)


@pytest.mark.asyncio
async def test_lote_de_otro_usuario_se_rechaza() -> None:
    """Un lote cuyo profile_id no es el del Usuario autenticado se rechaza (anti-BOLA)."""
    from app.common.errors import ForbiddenError

    user_id = uuid.uuid4()
    otro = uuid.uuid4()
    path_id = uuid.uuid4()
    batch = SyncBatchRequest(profile_id=otro, actions=[_finalizacion(path_id, "mc-1")])
    sesion = _FakeSession()

    with pytest.raises(ForbiddenError):
        await service.apply_batch(sesion, user_id, batch)
    assert len(sesion.actions) == 0
