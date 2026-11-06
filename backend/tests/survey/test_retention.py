"""Pruebas de la retención/anonimización de respuestas de encuesta (Req 20.8).

No usan BD real: un stub de sesión en memoria simula `scalars`/`commit`. El
reloj se controla con el parámetro `ahora` del servicio. Mirror del patrón de
`tests/profile/test_retention.py`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.common.config import get_settings
from app.survey import retention
from app.survey.models import SurveyResponse

_RETENCION_DIAS = get_settings().data_retention_days


class _FakeResult:
    """Resultado iterable que imita lo devuelto por `AsyncSession.scalars`."""

    def __init__(self, items: list[SurveyResponse]) -> None:
        self._items = items

    def __iter__(self):
        return iter(self._items)


class _FakeSession:
    """Sesión async que filtra las respuestas vencidas en memoria.

    Reproduce la condición del servicio: `created_at <= umbral` y respuesta no
    anonimizada aún (enlace con Perfil intacto).
    """

    def __init__(self, respuestas: list[SurveyResponse], umbral: datetime) -> None:
        self._respuestas = respuestas
        self._umbral = umbral
        self.commits = 0

    async def scalars(self, _stmt) -> _FakeResult:
        vencidas = [
            r
            for r in self._respuestas
            if r.created_at <= self._umbral and r.profile_id != retention.ANON_PROFILE_ID
        ]
        return _FakeResult(vencidas)

    async def commit(self) -> None:
        self.commits += 1


def _respuesta(created_at: datetime) -> SurveyResponse:
    return SurveyResponse(
        id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        path_id=uuid.uuid4(),
        rating=4,
        answers={"comentario": "me gustó la ruta, vivo en la vereda El Progreso"},
        geo_zone="zona-1",
        client_event_id=uuid.uuid4(),
        created_at=created_at,
    )


# Feature: cima-plataforma, retención de respuestas de encuesta.
# Validates: Requirements 20.8
@settings(max_examples=100, deadline=None)
@given(dias=st.integers(min_value=0, max_value=400))
@pytest.mark.asyncio
async def test_anonimizacion_por_antiguedad(dias: int) -> None:
    """El enlace y el texto libre se anonimizan si y solo si antigüedad ≥ retención."""
    ahora = datetime(2026, 6, 1, tzinfo=timezone.utc)
    respuesta = _respuesta(created_at=ahora - timedelta(days=dias))
    original_profile = respuesta.profile_id
    umbral = ahora - timedelta(days=_RETENCION_DIAS)
    sesion = _FakeSession([respuesta], umbral)

    await retention.anonimizar_respuestas_vencidas(sesion, ahora=ahora)

    if dias >= _RETENCION_DIAS:
        # Enlace con el Perfil roto y texto libre descartado.
        assert respuesta.profile_id == retention.ANON_PROFILE_ID
        assert respuesta.answers == {}
        # Campos agregables no identificables se conservan para el reporte por zona.
        assert respuesta.rating == 4
        assert respuesta.geo_zone == "zona-1"
    else:
        # Dentro de la ventana: todo intacto.
        assert respuesta.profile_id == original_profile
        assert respuesta.answers != {}


@pytest.mark.asyncio
async def test_retencion_es_idempotente() -> None:
    """Ejecutar la retención dos veces no re-procesa respuestas ya anonimizadas."""
    ahora = datetime(2026, 6, 1, tzinfo=timezone.utc)
    respuesta = _respuesta(created_at=ahora - timedelta(days=200))
    umbral = ahora - timedelta(days=_RETENCION_DIAS)
    sesion = _FakeSession([respuesta], umbral)

    primera = await retention.anonimizar_respuestas_vencidas(sesion, ahora=ahora)
    segunda = await retention.anonimizar_respuestas_vencidas(sesion, ahora=ahora)

    assert primera == 1
    assert segunda == 0  # ya anonimizada, no se vuelve a contar


@pytest.mark.asyncio
async def test_retencion_devuelve_conteo_de_anonimizadas() -> None:
    """El servicio devuelve cuántas respuestas anonimizó, conservando las vigentes."""
    ahora = datetime(2026, 6, 1, tzinfo=timezone.utc)
    umbral = ahora - timedelta(days=_RETENCION_DIAS)
    vencidas = [_respuesta(created_at=ahora - timedelta(days=120)) for _ in range(3)]
    vigente = _respuesta(created_at=ahora - timedelta(days=10))
    vigente_profile = vigente.profile_id
    sesion = _FakeSession([*vencidas, vigente], umbral)

    anonimizadas = await retention.anonimizar_respuestas_vencidas(sesion, ahora=ahora)

    assert anonimizadas == 3
    assert vigente.profile_id == vigente_profile
