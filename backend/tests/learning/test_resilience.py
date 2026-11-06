"""Pruebas de resiliencia del registro de eventos del Learning Service.

Feature: cima-plataforma.
- Property 15: resiliencia de registro con reintentos acotados (Req 4.7, 8.4). Para toda
  secuencia de fallos el número de reintentos no excede 3 y, de persistir el fallo, el
  evento se conserva para registro posterior sin pérdida de datos.

Metrics se reemplaza por un doble que falla según un guion y deduplica por
`client_event_id` como lo hace el real; la cola se simula en memoria.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy.exc import OperationalError

from app.learning import service
from app.learning.dto import FinalizeRequest
from app.learning.models import LearningEventOutbox
from app.metrics import service as metrics_service
from tests.learning.test_completion import _path, _progress, _Session

_EVENT = "microcapsula_completada"
# Valor fijado por la spec (Req 4.7, Property 15): 3 reintentos tras el primer intento.
# No se deriva de la constante del código para que cambiarla haga fallar la prueba.
_MAX_CALLS = 4


class _FakeMetrics:
    """Doble de Metrics: falla según un guion y registra de forma idempotente."""

    def __init__(self, failures: list[bool]) -> None:
        self._script = list(failures)
        self.calls = 0
        self.recorded: dict[uuid.UUID, str] = {}

    async def record_event(self, _db, data):  # noqa: ANN001, ANN201
        self.calls += 1
        if self._script and self._script.pop(0):
            raise OperationalError("INSERT", {}, Exception("base de datos no disponible"))
        self.recorded[data.client_event_id] = data.event_type


class _ResilientSession(_Session):
    """Sesión simulada con la cola de eventos en memoria y `rollback`."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        super().__init__(*args, **kwargs)
        self.outbox: dict[uuid.UUID, LearningEventOutbox] = {}
        self.rollbacks = 0

    async def scalar(self, stmt):  # noqa: ANN001, ANN201
        if "learning_event_outbox" in str(stmt):
            return self.outbox.get(next(iter(stmt.compile().params.values())))
        return await super().scalar(stmt)

    async def scalars(self, stmt):  # noqa: ANN001, ANN201
        if "learning_event_outbox" in str(stmt):
            return _Rows(list(self.outbox.values()))
        return await super().scalars(stmt)

    def add(self, obj) -> None:  # noqa: ANN001
        if isinstance(obj, LearningEventOutbox):
            obj.id = obj.id or uuid.uuid4()
            self.outbox[obj.client_event_id] = obj
            return
        super().add(obj)

    async def execute(self, stmt):  # noqa: ANN001, ANN201
        row_id = next(iter(stmt.compile().params.values()))
        for key, row in list(self.outbox.items()):
            if row.id == row_id:
                del self.outbox[key]

    async def rollback(self) -> None:
        self.rollbacks += 1


class _Rows:
    def __init__(self, items: list) -> None:  # noqa: ANN001
        self._items = items

    def all(self) -> list:
        return list(self._items)


def _record(session, user, event_id):  # noqa: ANN001, ANN201
    return service._record_event_resilient(session, user, _EVENT, event_id)


# --------------------------------------------------------------------------- #
# Property 15 — Resiliencia de registro con reintentos acotados (Req 4.7, 8.4)
# --------------------------------------------------------------------------- #
@settings(max_examples=60, deadline=None)
@given(failures=st.lists(st.booleans(), max_size=10))
@pytest.mark.asyncio
async def test_property_15_reintentos_acotados_y_evento_conservado(
    failures: list[bool],
) -> None:
    """Para toda secuencia de fallos: ≤ 3 reintentos y el evento nunca se pierde."""
    # Given una secuencia arbitraria de fallos de registro
    metrics, session = _FakeMetrics(failures), _ResilientSession(None)
    user, event_id = uuid.uuid4(), uuid.uuid4()

    # When se registra el evento
    with patch.object(metrics_service, "record_event", metrics.record_event):
        await _record(session, user, event_id)

    # Then no hay más de 3 reintentos (4 intentos en total)
    assert 1 <= metrics.calls <= _MAX_CALLS
    # Y el evento queda registrado o conservado en la cola, nunca en ambos ni en ninguno
    assert (event_id in metrics.recorded) != (event_id in session.outbox)
    # Y solo se conserva si los 4 intentos fallaron
    all_failed = len(failures) >= _MAX_CALLS and all(failures[:_MAX_CALLS])
    assert (event_id in session.outbox) == all_failed

    # Y, recuperada la base de datos, la cola lo registra exactamente una vez
    healthy = _FakeMetrics([])
    with patch.object(metrics_service, "record_event", healthy.record_event):
        await service.drain_outbox(session, user)
    assert session.outbox == {}
    assert event_id in {**metrics.recorded, **healthy.recorded}


# --------------------------------------------------------------------------- #
# Reintentos y cola
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_fallo_transitorio_se_recupera_sin_usar_la_cola() -> None:
    """Un fallo seguido de un éxito se resuelve con reintentos y no toca la cola."""
    metrics, session = _FakeMetrics([True, True]), _ResilientSession(None)
    event_id = uuid.uuid4()

    with patch.object(metrics_service, "record_event", metrics.record_event):
        await _record(session, uuid.uuid4(), event_id)

    assert metrics.calls == 3
    assert event_id in metrics.recorded
    assert session.outbox == {}
    assert session.rollbacks == 2


@pytest.mark.asyncio
async def test_fallo_persistente_hace_cuatro_intentos_y_conserva_el_evento() -> None:
    """Persistiendo el fallo: 1 intento + 3 reintentos y luego se encola."""
    metrics, session = _FakeMetrics([True] * 20), _ResilientSession(None)
    user, event_id = uuid.uuid4(), uuid.uuid4()

    with patch.object(metrics_service, "record_event", metrics.record_event):
        await _record(session, user, event_id)

    assert metrics.calls == 4
    assert metrics.recorded == {}
    queued = session.outbox[event_id]
    assert (queued.profile_id, queued.event_type) == (user, _EVENT)


@pytest.mark.asyncio
async def test_encolar_el_mismo_evento_dos_veces_no_lo_duplica() -> None:
    """La cola es idempotente por `client_event_id`."""
    session, user, event_id = _ResilientSession(None), uuid.uuid4(), uuid.uuid4()

    await service._enqueue_event(session, user, _EVENT, event_id)
    await service._enqueue_event(session, user, _EVENT, event_id)

    assert len(session.outbox) == 1


@pytest.mark.asyncio
async def test_un_error_que_no_es_de_base_de_datos_no_se_oculta() -> None:
    """Solo se reintentan errores de base de datos; un defecto se propaga sin encolar."""

    async def _defect(_db, _data):  # noqa: ANN001, ANN202
        raise RuntimeError("defecto")

    session = _ResilientSession(None)
    with patch.object(metrics_service, "record_event", _defect):
        with pytest.raises(RuntimeError):
            await _record(session, uuid.uuid4(), uuid.uuid4())

    assert session.outbox == {}


# --------------------------------------------------------------------------- #
# drain_outbox
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_drain_registra_los_pendientes_y_los_quita_de_la_cola() -> None:
    """`drain_outbox` registra cada evento pendiente y lo borra de la cola."""
    session, user = _ResilientSession(None), uuid.uuid4()
    ids = [uuid.uuid4() for _ in range(3)]
    for event_id in ids:
        await service._enqueue_event(session, user, _EVENT, event_id)
    metrics = _FakeMetrics([])

    with patch.object(metrics_service, "record_event", metrics.record_event):
        drained = await service.drain_outbox(session, user)

    assert drained == 3
    assert set(metrics.recorded) == set(ids)
    assert session.outbox == {}


@pytest.mark.asyncio
async def test_drain_se_detiene_en_el_primer_fallo_y_conserva_el_resto() -> None:
    """Si Metrics sigue caído, el drenaje no insiste y no pierde ningún evento."""
    session, user = _ResilientSession(None), uuid.uuid4()
    ids = [uuid.uuid4() for _ in range(3)]
    for event_id in ids:
        await service._enqueue_event(session, user, _EVENT, event_id)
    metrics = _FakeMetrics([False, True])

    with patch.object(metrics_service, "record_event", metrics.record_event):
        drained = await service.drain_outbox(session, user)

    assert drained == 1
    assert metrics.calls == 2
    assert len(session.outbox) == 2


# --------------------------------------------------------------------------- #
# Integración con la finalización
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_la_finalizacion_no_falla_si_metrics_esta_caido_y_luego_se_recupera() -> None:
    """Con Metrics caído la finalización responde bien, encola y la siguiente recupera."""
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    session = _ResilientSession(path, _progress(user, path, [c1]))
    down = _FakeMetrics([True] * 50)

    with patch.object(metrics_service, "record_event", down.record_event):
        resp = await service.finalize_microcapsule(
            session, user, c2, FinalizeRequest(client_event_id=uuid.uuid4(), path_id=path.id)
        )

    # La respuesta es correcta y los dos eventos (cápsula y ruta) quedaron en la cola.
    assert resp.path_completed is True
    assert sorted(e.event_type for e in session.outbox.values()) == [
        "microcapsula_completada",
        "ruta_completada",
    ]

    healthy = _FakeMetrics([])
    with patch.object(metrics_service, "record_event", healthy.record_event):
        await service.finalize_microcapsule(
            session, user, c2, FinalizeRequest(client_event_id=uuid.uuid4(), path_id=path.id)
        )

    # La siguiente finalización drenó la cola: no queda nada pendiente.
    assert session.outbox == {}
    assert "ruta_completada" in healthy.recorded.values()
