"""Pruebas del limitador de tasa con ventana deslizante.

Feature: cima-plataforma, Property 33: Rate limiting en componentes core.

Son pruebas puras: no requieren base de datos. El reloj se inyecta con el
parámetro `now` para controlar la ventana de forma determinista.
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.common.rate_limit import SlidingWindowRateLimiter


# Feature: cima-plataforma, Property 33: Rate limiting en componentes core.
# Validates: Requirements 9.7, 12.2, 12.5
@settings(max_examples=100, deadline=None)
@given(
    max_hits=st.integers(min_value=1, max_value=20),
    total=st.integers(min_value=0, max_value=40),
)
def test_property_33_dentro_del_limite_pasa_y_excedente_se_rechaza(
    max_hits: int, total: int
) -> None:
    """En una ráfaga instantánea, los primeros `max_hits` pasan y el resto se rechaza."""
    limiter = SlidingWindowRateLimiter(max_hits=max_hits, window_seconds=60)
    permitidos = sum(1 for _ in range(total) if limiter.allow("actor", now=1000.0))
    # Se procesan exactamente min(total, max_hits); las excedentes se rechazan.
    assert permitidos == min(total, max_hits)


def test_ventana_se_reinicia_al_pasar_el_tiempo() -> None:
    """Pasada la ventana, los intentos vuelven a permitirse (ventana deslizante)."""
    limiter = SlidingWindowRateLimiter(max_hits=2, window_seconds=10)
    assert limiter.allow("a", now=0.0) is True
    assert limiter.allow("a", now=1.0) is True
    assert limiter.allow("a", now=2.0) is False  # excede dentro de la ventana
    # Tras superar la ventana (t > 10 desde el primer hit), vuelve a permitir.
    assert limiter.allow("a", now=12.0) is True


def test_claves_distintas_se_limitan_de_forma_independiente() -> None:
    """El límite es por clave: un actor saturado no afecta a otro."""
    limiter = SlidingWindowRateLimiter(max_hits=1, window_seconds=60)
    assert limiter.allow("actor-1", now=5.0) is True
    assert limiter.allow("actor-1", now=5.0) is False
    # Otra clave tiene su propio presupuesto.
    assert limiter.allow("actor-2", now=5.0) is True


def test_reset_limpia_el_conteo_de_una_clave() -> None:
    """`reset` devuelve a la clave su presupuesto completo."""
    limiter = SlidingWindowRateLimiter(max_hits=1, window_seconds=60)
    assert limiter.allow("a", now=1.0) is True
    assert limiter.allow("a", now=1.0) is False
    limiter.reset("a")
    assert limiter.allow("a", now=1.0) is True


@pytest.mark.parametrize("bad", [0, -1])
def test_constructor_rechaza_parametros_invalidos(bad: int) -> None:
    """El constructor valida sus parámetros (max_hits >= 1, window > 0)."""
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(max_hits=bad, window_seconds=60)
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(max_hits=1, window_seconds=bad)
