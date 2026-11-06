"""Pruebas de propiedad del reporte agregado del Metrics Service.

Feature: cima-plataforma
- Property 27: k-anonimato en reportes agregados (Tarea 18.5, Req 8.6, 15.4).
- Property 28: Reportes sin PII individual (Tarea 18.6, Req 8.5, 15.3).

El stub de sesión agrega los eventos en memoria replicando la semántica de la
consulta del servicio (agrupar por zona y tipo, contar eventos y Usuarios
distintos, suprimir grupos con < K_ANONYMITY_THRESHOLD Usuarios distintos).
"""
from __future__ import annotations

import uuid
from collections import defaultdict

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.metrics import service
from app.metrics.constants import K_ANONYMITY_THRESHOLD
from app.metrics.dto import ZoneAggregate


class _Row:
    """Fila agregada equivalente a la que devuelve la consulta del servicio."""

    def __init__(self, geo_zone: str, event_type: str, event_count: int, distinct_users: int):
        self.geo_zone = geo_zone
        self.event_type = event_type
        self.event_count = event_count
        self.distinct_users = distinct_users


class _AggSession:
    """Sesión async cuyo `execute` agrega eventos como lo haría la BD.

    Recibe tuplas (geo_zone, event_type, profile_id), agrupa por (zona, tipo),
    cuenta eventos y Usuarios distintos y suprime los grupos con menos de
    `K_ANONYMITY_THRESHOLD` Usuarios distintos (Req 8.6).
    """

    def __init__(self, eventos: list[tuple[str, str, uuid.UUID]]) -> None:
        self._eventos = eventos

    async def execute(self, _stmt):
        grupos: dict[tuple[str, str], list[uuid.UUID]] = defaultdict(list)
        for zona, tipo, pid in self._eventos:
            grupos[(zona, tipo)].append(pid)

        filas = []
        for (zona, tipo), pids in sorted(grupos.items()):
            distintos = len(set(pids))
            if distintos >= K_ANONYMITY_THRESHOLD:
                filas.append(
                    _Row(zona, tipo, event_count=len(pids), distinct_users=distintos)
                )
        return iter(filas)


# Feature: cima-plataforma, Property 27: k-anonimato en reportes agregados.
# Validates: Requirements 8.6, 15.4
@settings(max_examples=100, deadline=None)
@given(usuarios_zona_a=st.integers(min_value=0, max_value=12))
@pytest.mark.asyncio
async def test_property_27_k_anonimato(usuarios_zona_a: int) -> None:
    """Una zona aparece en el reporte si y solo si tiene ≥ K Usuarios distintos."""
    eventos: list[tuple[str, str, uuid.UUID]] = [
        ("zona-a", "ruta_completada", uuid.uuid4()) for _ in range(usuarios_zona_a)
    ]
    sesion = _AggSession(eventos)

    reporte = await service.build_report(sesion)

    zona_a = [agg for agg in reporte.aggregates if agg.geo_zone == "zona-a"]
    if usuarios_zona_a >= K_ANONYMITY_THRESHOLD:
        assert len(zona_a) == 1
        assert zona_a[0].distinct_users == usuarios_zona_a
    else:
        # Zona suprimida: no aparece en el reporte.
        assert zona_a == []


@pytest.mark.asyncio
async def test_property_27_zona_en_el_limite_aparece() -> None:
    """Una zona con exactamente K Usuarios distintos no se suprime."""
    eventos = [
        ("zona-b", "microcapsula_completada", uuid.uuid4())
        for _ in range(K_ANONYMITY_THRESHOLD)
    ]
    reporte = await service.build_report(_AggSession(eventos))
    assert any(agg.geo_zone == "zona-b" for agg in reporte.aggregates)


# Feature: cima-plataforma, Property 28: Reportes sin PII individual.
# Validates: Requirements 8.5, 15.3
@pytest.mark.asyncio
async def test_property_28_reporte_sin_pii_individual() -> None:
    """El reporte solo contiene campos agregados; ningún identificador de Perfil."""
    eventos = [
        ("zona-c", "ruta_completada", uuid.uuid4())
        for _ in range(K_ANONYMITY_THRESHOLD + 2)
    ]
    reporte = await service.build_report(_AggSession(eventos))

    assert len(reporte.aggregates) >= 1
    campos_permitidos = set(ZoneAggregate.model_fields.keys())
    # El DTO de agregado no expone profile_id ni ningún campo identificable.
    assert "profile_id" not in campos_permitidos
    assert campos_permitidos == {"geo_zone", "event_type", "event_count", "distinct_users"}
    for agg in reporte.aggregates:
        dump = agg.model_dump()
        assert "profile_id" not in dump
        assert set(dump.keys()) == campos_permitidos
