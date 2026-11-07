"""Pruebas del nivel, la racha, el resumen y el ranking de Gamification.

Extensión de experiencia no especificada en requirements.md (el Req 19 solo exige
puntos e Insignias). Verifican que las reglas viven en el backend (Req 19.3), que la
titularidad sale de la sesión y que el ranking no expone PII (Req 19.7, 19.8).

La racha atómica (`INSERT ... ON CONFLICT`) se verifica contra Postgres real; aquí se
cubre la lógica pura y la forma de las respuestas con sesiones simuladas.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.gamification import service
from app.gamification.constants import LEVELS, RECOGNITION_RULES

_HOY = date(2026, 11, 6)


# --------------------------------------------------------------------------- #
# Nivel
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("puntos", "nivel"),
    [(0, 1), (49, 1), (50, 2), (149, 2), (150, 3), (299, 3), (300, 4), (600, 5), (99_999, 5), (-10, 1)],
)
def test_el_nivel_corresponde_a_los_puntos(puntos: int, nivel: int) -> None:
    """Cada umbral de puntos marca el cambio de nivel; el máximo no tiene siguiente."""
    actual, siguiente = service.level_for(puntos)

    assert actual.number == nivel
    assert (siguiente is None) == (nivel == LEVELS[-1].number)


@given(puntos=st.integers(min_value=0, max_value=100_000))
def test_property_el_nivel_es_coherente_con_sus_umbrales(puntos: int) -> None:
    """El nivel nunca exige más puntos de los que se tienen y el siguiente sí los supera."""
    actual, siguiente = service.level_for(puntos)

    assert actual.min_points <= puntos
    assert siguiente is None or siguiente.min_points > puntos
    assert 0 <= service._level_progress_pct(puntos, actual, siguiente) <= 100


@given(a=st.integers(min_value=0, max_value=5_000), b=st.integers(min_value=0, max_value=5_000))
def test_property_mas_puntos_nunca_baja_el_nivel(a: int, b: int) -> None:
    """El nivel es monótono: quien tiene más puntos no queda en un nivel menor."""
    menor, mayor = sorted((a, b))

    assert service.level_for(menor)[0].number <= service.level_for(mayor)[0].number


def test_el_progreso_hacia_el_siguiente_nivel_es_proporcional() -> None:
    """A mitad de camino entre 50 y 150 puntos el avance es 50 %; en el máximo es 100 %."""
    actual, siguiente = service.level_for(100)
    assert service._level_progress_pct(100, actual, siguiente) == 50

    maximo, sin_siguiente = service.level_for(10_000)
    assert service._level_progress_pct(10_000, maximo, sin_siguiente) == 100


# --------------------------------------------------------------------------- #
# Racha
# --------------------------------------------------------------------------- #
def _fila(racha: int, ultimo: date | None, puntos: int = 0, perfil: uuid.UUID | None = None):  # noqa: ANN202
    return SimpleNamespace(
        profile_id=perfil or uuid.uuid4(),
        total_points=puntos,
        current_streak=racha,
        last_activity_date=ultimo,
    )


@pytest.mark.parametrize(
    ("ultimo", "esperada"),
    [(_HOY, 4), (_HOY - timedelta(days=1), 4), (_HOY - timedelta(days=2), 0), (None, 0)],
)
def test_la_racha_mostrada_se_rompe_pasado_un_dia_sin_actividad(
    ultimo: date | None, esperada: int
) -> None:
    """Hoy o ayer mantienen la racha; con más de un día sin actividad se muestra 0."""
    assert service._effective_streak(_fila(4, ultimo), _HOY) == esperada


def test_sin_fila_de_puntos_la_racha_es_cero() -> None:
    """Un Usuario sin actividad registrada no tiene racha."""
    assert service._effective_streak(None, _HOY) == 0


# --------------------------------------------------------------------------- #
# Ranking
# --------------------------------------------------------------------------- #
def test_quienes_empatan_en_puntos_comparten_posicion() -> None:
    """Posición de competencia: 100, 100, 50 -> 1, 1, 3."""
    assert service._competition_ranks([100, 100, 50]) == [1, 1, 3]
    assert service._competition_ranks([]) == []
    assert service._competition_ranks([30, 20, 10]) == [1, 2, 3]


def test_el_alias_es_estable_y_no_revela_el_identificador() -> None:
    """El mismo Perfil siempre tiene el mismo alias, y el alias no contiene su id."""
    perfil, otro = uuid.uuid4(), uuid.uuid4()

    alias = service.pseudonym(perfil)

    assert alias == service.pseudonym(perfil)
    assert alias.startswith("Participante ")
    assert str(perfil) not in alias
    assert str(perfil).replace("-", "") not in alias
    assert len(alias) == len("Participante ") + 4
    assert service.pseudonym(otro).startswith("Participante ")


class _SesionRanking:
    """Sesión mínima: `scalars` devuelve el top y `scalar` los conteos en orden."""

    def __init__(self, top: list, conteos: list[int]) -> None:  # noqa: ANN001
        self._top = top
        self._conteos = list(conteos)

    async def scalars(self, _stmt):  # noqa: ANN001, ANN201
        return SimpleNamespace(all=lambda: list(self._top))

    async def scalar(self, _stmt):  # noqa: ANN001, ANN201
        return self._conteos.pop(0)


@pytest.mark.asyncio
async def test_el_ranking_marca_al_titular_y_no_expone_identificadores() -> None:
    """El titular aparece resaltado y ninguna fila contiene ids, teléfonos ni nombres."""
    yo, otro = uuid.uuid4(), uuid.uuid4()
    top = [_fila(5, _HOY, 300, otro), _fila(2, _HOY, 60, yo)]
    sesion = _SesionRanking(top, conteos=[2])

    ranking = await service.get_leaderboard(sesion, yo, size=10, today=_HOY)

    assert [e.rank for e in ranking.entries] == [1, 2]
    assert [e.is_me for e in ranking.entries] == [False, True]
    assert ranking.me is not None and ranking.me.rank == 2
    assert ranking.participants == 2
    volcado = ranking.model_dump_json()
    assert str(yo) not in volcado and str(otro) not in volcado


@pytest.mark.asyncio
async def test_si_el_titular_queda_fuera_del_top_se_calcula_su_posicion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fuera del top, su posición es 1 + cuántos tienen estrictamente más puntos."""
    yo = uuid.uuid4()
    top = [_fila(1, _HOY, 500), _fila(1, _HOY, 400)]
    sesion = _SesionRanking(top, conteos=[12, 7])

    async def _mis_puntos(_db, _perfil):  # noqa: ANN001, ANN202
        return _fila(1, _HOY, 20, yo)

    monkeypatch.setattr(service, "_get_points", _mis_puntos)

    ranking = await service.get_leaderboard(sesion, yo, size=2, today=_HOY)

    assert ranking.me is not None
    assert ranking.me.rank == 8 and ranking.me.is_me is True
    assert ranking.participants == 12
    assert all(not e.is_me for e in ranking.entries)


@pytest.mark.asyncio
async def test_quien_no_tiene_puntos_no_aparece_en_el_ranking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin puntos no hay posición propia (`me` es None)."""
    yo = uuid.uuid4()
    sesion = _SesionRanking([], conteos=[0])

    async def _sin_puntos(_db, _perfil):  # noqa: ANN001, ANN202
        return None

    monkeypatch.setattr(service, "_get_points", _sin_puntos)

    ranking = await service.get_leaderboard(sesion, yo, today=_HOY)

    assert ranking.entries == [] and ranking.me is None and ranking.participants == 0


# --------------------------------------------------------------------------- #
# Resumen
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_el_resumen_combina_puntos_nivel_racha_e_insignias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El resumen marca las Insignias ganadas y calcula nivel y racha en el backend."""
    yo = uuid.uuid4()

    async def _puntos(_db, _perfil, lock=False):  # noqa: ANN001, ANN202
        return _fila(3, _HOY, 60, yo)

    async def _insignias(_db, _perfil):  # noqa: ANN001, ANN202
        return [SimpleNamespace(badge_code="primer_paso")]

    monkeypatch.setattr(service, "_get_points", _puntos)
    monkeypatch.setattr(service, "_list_badges", _insignias)

    resumen = await service.get_summary(object(), yo, today=_HOY)  # type: ignore[arg-type]

    assert resumen.total_points == 60 and resumen.streak_days == 3
    assert resumen.level.number == 2
    assert resumen.next_level is not None and resumen.next_level.points_needed == 90
    ganadas = {b.badge_code: b.earned for b in resumen.badges}
    assert ganadas == {rule.code: rule.code == "primer_paso" for rule in RECOGNITION_RULES.values()}
    assert str(yo) not in resumen.model_dump_json()


@pytest.mark.asyncio
async def test_un_usuario_nuevo_empieza_en_el_primer_nivel_sin_racha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin fila de puntos ni Insignias: 0 puntos, nivel 1, racha 0 y nada ganado."""

    async def _nada(_db, _perfil, lock=False):  # noqa: ANN001, ANN202
        return None

    async def _sin_insignias(_db, _perfil):  # noqa: ANN001, ANN202
        return []

    monkeypatch.setattr(service, "_get_points", _nada)
    monkeypatch.setattr(service, "_list_badges", _sin_insignias)

    resumen = await service.get_summary(object(), uuid.uuid4(), today=_HOY)  # type: ignore[arg-type]

    assert (resumen.total_points, resumen.streak_days, resumen.level.number) == (0, 0, 1)
    assert not any(b.earned for b in resumen.badges)
