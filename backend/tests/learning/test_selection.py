"""Pruebas de la selección personalizada de microcápsulas.

Feature: cima-plataforma.
- Property 10: invariante de duración (180–300 s).
- Property 11: clasificación temática única (allowlist).
- Property 12: selección acotada (≤ 10) y ordenada por relevancia y fecha.
- Property 13: fallback a tema general sin coincidencias.

No usan BD real: un stub de sesión async simula el subconjunto del ORM que
consume el service (execute → scalars().all()).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError as PydanticValidationError

from app.learning import service
from app.learning.constants import (
    ALLOWED_TOPICS,
    FALLBACK_TOPIC,
    MAX_DURATION_SEC,
    MAX_SELECTION,
    MIN_DURATION_SEC,
)
from app.learning.dto import MicrocapsuleResponse
from app.learning.models import Microcapsule
from app.learning.service import _ordered_top

_BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _capsule(
    *,
    topic: str = FALLBACK_TOPIC,
    tags: list[str] | None = None,
    duration: int = 200,
    relevance: float = 1.0,
    published_offset: int = 0,
) -> Microcapsule:
    """Construye una microcápsula de prueba (como estaría en BD)."""
    return Microcapsule(
        id=uuid.uuid4(),
        topic=topic,
        activity_tags=tags if tags is not None else ["cafe"],
        duration_sec=duration,
        relevance=Decimal(str(relevance)),
        difficulty=0,
        published_at=_BASE_TIME + timedelta(days=published_offset),
    )


class _ScalarsResult:
    def __init__(self, items: list[Microcapsule]) -> None:
        self._items = items

    def scalars(self):  # noqa: ANN201 - imita la API de SQLAlchemy Result
        return self

    def all(self) -> list[Microcapsule]:
        return self._items


class _FakeSession:
    """Sesión async mínima: `execute` devuelve siempre el mismo conjunto."""

    def __init__(self, items: list[Microcapsule]) -> None:
        self._items = items

    async def execute(self, _stmt) -> _ScalarsResult:
        return _ScalarsResult(self._items)


# --------------------------------------------------------------------------- #
# Property 10 — Invariante de duración de microcápsula (Req 4.1)
# --------------------------------------------------------------------------- #
@given(duration=st.integers(min_value=MIN_DURATION_SEC, max_value=MAX_DURATION_SEC))
def test_property_10_duracion_valida_se_acepta(duration: int) -> None:
    """Toda duración en [180, 300] se acepta en el DTO de salida."""
    dto = MicrocapsuleResponse(
        id=uuid.uuid4(),
        topic=FALLBACK_TOPIC,
        activity_tags=["cafe"],
        duration_sec=duration,
        difficulty=0,
    )
    assert MIN_DURATION_SEC <= dto.duration_sec <= MAX_DURATION_SEC


@given(
    duration=st.integers().filter(
        lambda d: d < MIN_DURATION_SEC or d > MAX_DURATION_SEC
    )
)
def test_property_10_duracion_fuera_de_rango_se_rechaza(duration: int) -> None:
    """Toda duración fuera de [180, 300] es rechazada por el DTO (Req 4.1)."""
    with pytest.raises(PydanticValidationError):
        MicrocapsuleResponse(
            id=uuid.uuid4(),
            topic=FALLBACK_TOPIC,
            activity_tags=["cafe"],
            duration_sec=duration,
            difficulty=0,
        )


# --------------------------------------------------------------------------- #
# Property 11 — Clasificación temática única (Req 4.2)
# --------------------------------------------------------------------------- #
@given(topic=st.sampled_from(sorted(ALLOWED_TOPICS)))
def test_property_11_tema_de_allowlist_se_acepta(topic: str) -> None:
    """Un tema de la allowlist se acepta."""
    dto = MicrocapsuleResponse(
        id=uuid.uuid4(), topic=topic, activity_tags=[], duration_sec=200, difficulty=0
    )
    assert dto.topic in ALLOWED_TOPICS


@given(topic=st.text(min_size=1, max_size=20).filter(lambda t: t not in ALLOWED_TOPICS))
def test_property_11_tema_fuera_de_allowlist_se_rechaza(topic: str) -> None:
    """Un tema fuera de la allowlist se rechaza (Req 4.2)."""
    with pytest.raises(PydanticValidationError):
        MicrocapsuleResponse(
            id=uuid.uuid4(), topic=topic, activity_tags=[], duration_sec=200, difficulty=0
        )


# --------------------------------------------------------------------------- #
# Property 12 — Selección acotada (≤ 10) y ordenada (Req 4.3)
# --------------------------------------------------------------------------- #
@settings(max_examples=50, deadline=None)
@given(
    data=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=4),  # relevancia (con empates)
            st.integers(min_value=0, max_value=30),  # offset de fecha
        ),
        min_size=1,
        max_size=25,
    )
)
def test_property_12_orden_relevancia_luego_fecha(
    data: list[tuple[int, int]],
) -> None:
    """`_ordered_top` ordena por relevancia desc. y, a igual relevancia, por fecha desc."""
    # Given un conjunto de cápsulas con relevancia y fecha variadas
    capsules = [
        _capsule(relevance=float(rel), published_offset=off) for rel, off in data
    ]

    # When se ordenan y acotan con el criterio del servicio
    top = _ordered_top(capsules)

    # Then no hay más de 10 (Req 4.3)
    assert len(top) <= MAX_SELECTION
    # And cada par consecutivo respeta relevancia desc. y fecha desc. como desempate
    for prev, nxt in zip(top, top[1:]):
        prev_key = (float(prev.relevance), prev.published_at)
        nxt_key = (float(nxt.relevance), nxt.published_at)
        assert prev_key >= nxt_key


@settings(max_examples=30, deadline=None)
@given(n=st.integers(min_value=11, max_value=25))
@pytest.mark.asyncio
async def test_property_12_seleccion_personalizada_acotada(n: int) -> None:
    """La selección personalizada por actividad entrega como máximo 10 cápsulas."""
    # Given n (>10) cápsulas que aplican a la actividad "cafe"
    capsules = [
        _capsule(topic="finanzas", tags=["cafe"], relevance=float(i), published_offset=i)
        for i in range(n)
    ]
    session = _FakeSession(capsules)

    # When se seleccionan para la actividad "cafe"
    result = await service.select_microcapsules(session, "cafe")

    # Then se entregan exactamente 10 (acotación) y no es fallback (Req 4.3)
    assert len(result.items) == MAX_SELECTION
    assert result.fallback is False


# --------------------------------------------------------------------------- #
# Property 13 — Fallback a tema general sin coincidencias (Req 4.4, 4.5, 4.9)
# --------------------------------------------------------------------------- #
class _ActivityTopicSession:
    """Stub que separa la consulta por actividad de la de tema.

    `_fetch_by_activity` no encuentra coincidencias (lista vacía) y
    `_fetch_by_topic` devuelve las cápsulas del tema general: así se ejercita el
    camino de fallback real del service (Req 4.4).
    """

    def __init__(self, by_activity: list[Microcapsule], by_topic: list[Microcapsule]) -> None:
        self._by_activity = by_activity
        self._by_topic = by_topic
        self._calls = 0

    async def execute(self, _stmt) -> _ScalarsResult:
        # La primera llamada del service es la de actividad; la siguiente, la de tema.
        self._calls += 1
        if self._calls == 1:
            return _ScalarsResult(self._by_activity)
        return _ScalarsResult(self._by_topic)


@pytest.mark.asyncio
async def test_property_13_fallback_sin_coincidencias() -> None:
    """Sin cápsulas para la actividad, se entrega el tema general + notificación."""
    # Given una actividad sin coincidencias y un catálogo general disponible
    general = [_capsule(topic=FALLBACK_TOPIC, tags=["general"]) for _ in range(3)]
    session = _ActivityTopicSession(by_activity=[], by_topic=general)

    # When se seleccionan para una actividad sin coincidencias
    result = await service.select_microcapsules(session, "mango")

    # Then todas las cápsulas son del tema general y se marca la notificación (Req 4.4, 4.5)
    assert result.fallback is True
    assert result.notice is not None
    assert result.items
    assert all(c.topic == FALLBACK_TOPIC for c in result.items)


@pytest.mark.asyncio
async def test_perfil_incompleto_solicita_actividad() -> None:
    """Sin actividad en el Perfil, se pide la actividad y se entrega tema general (Req 4.8, 4.9)."""
    # Given un catálogo con cápsulas del tema general
    general = [_capsule(topic=FALLBACK_TOPIC, tags=["general"]) for _ in range(2)]
    session = _FakeSession(general)

    # When la actividad es None (perfil incompleto)
    result = await service.select_microcapsules(session, None)

    # Then se marca prompt_activity y fallback con el tema general
    assert result.prompt_activity is True
    assert result.fallback is True
    assert all(c.topic == FALLBACK_TOPIC for c in result.items)
