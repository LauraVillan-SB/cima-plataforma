"""Prueba de propiedad de la asignación de zona en eventos de métrica.

Feature: cima-plataforma, Property 26: Asignación de zona en eventos de métrica.
Validates: Requirements 8.1, 8.2

Un evento con zona se registra clasificado con esa zona; un evento sin zona se
registra como no clasificado con el marcador "sin_zona". El stub de sesión
imita el registro idempotente por `client_event_id` sin BD real.
"""
from __future__ import annotations

import uuid

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.metrics import service
from app.metrics.constants import UNCLASSIFIED_ZONE
from app.metrics.dto import MetricEventCreate
from app.metrics.models import MetricEvent


class _FakeSession:
    """Sesión async mínima que imita el almacén de `metric_events`."""

    def __init__(self) -> None:
        self.events: list[MetricEvent] = []
        self.commits = 0

    async def scalar(self, stmt):
        event_id = _bind_value(stmt, "client_event_id")
        return next(
            (e for e in self.events if str(e.client_event_id) == str(event_id)),
            None,
        )

    def add(self, obj: MetricEvent) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        self.events.append(obj)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _obj) -> None:
        return None


def _bind_value(stmt, column: str):
    params = stmt.compile().params
    for key, value in params.items():
        if key.startswith(column):
            return value
    return None


# Feature: cima-plataforma, Property 26: Asignación de zona en eventos de métrica.
# Validates: Requirements 8.1, 8.2
@settings(max_examples=100, deadline=None)
@given(
    con_zona=st.booleans(),
    # Alfabeto restringido a letras y dígitos para que la zona siempre tenga
    # contenido no vacío tras la normalización del DTO.
    zona=st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")), min_size=1, max_size=100),
)
@pytest.mark.asyncio
async def test_property_26_asignacion_de_zona(con_zona: bool, zona: str) -> None:
    """Con zona → clasificado con la zona normalizada; sin zona → "sin_zona"."""
    sesion = _FakeSession()
    data = MetricEventCreate(
        client_event_id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        event_type="microcapsula_completada",
        geo_zone=zona if con_zona else None,
    )

    resultado = await service.record_event(sesion, data)

    if con_zona:
        assert resultado.classified is True
        # El servicio conserva la zona ya normalizada por el DTO.
        assert resultado.geo_zone == data.geo_zone
        assert resultado.geo_zone != UNCLASSIFIED_ZONE
    else:
        assert resultado.classified is False
        assert resultado.geo_zone == UNCLASSIFIED_ZONE


@pytest.mark.asyncio
async def test_registro_es_idempotente_por_client_event_id() -> None:
    """Reusar el mismo `client_event_id` devuelve el evento ya registrado."""
    sesion = _FakeSession()
    event_id = uuid.uuid4()
    data = MetricEventCreate(
        client_event_id=event_id,
        profile_id=uuid.uuid4(),
        event_type="ruta_completada",
        geo_zone="zona-1",
    )

    primera = await service.record_event(sesion, data)
    segunda = await service.record_event(sesion, data)

    assert primera.id == segunda.id
    assert len(sesion.events) == 1
