"""Pruebas de integración del circuit breaker, timeout y fallback (Tarea 10.5, parcial).

Requisitos 11.5 y 11.6: toda dependencia externa se envuelve con circuit breaker,
timeout bajo y fallback documentado; la activación se registra con el
Correlation-ID y sin PII. Se usan dependencias simuladas que fallan, se cuelgan
o se recuperan, y un reloj controlado para no depender de esperas reales.

La otra mitad de la 10.5 (escalado sin pérdida de sesión con almacén
compartido) depende de la 10.3 y no se cubre aquí.

Validates: Requirements 11.5, 11.6
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
from types import SimpleNamespace

import pytest

from app.common import resilience
from app.common.correlation import set_correlation_id
from app.common.logging import JsonFormatter
from app.common.resilience import (
    CircuitBreaker,
    CircuitoAbiertoError,
    DependenciaFallidaError,
    EstadoCircuito,
)

_UMBRAL = 3
_RESET = 30.0
# Placeholder con forma de celular colombiano; no es un dato real.
_PII = "3000000000"


class _Reloj:
    """Reemplaza `time.monotonic` del módulo para avanzar el tiempo a voluntad."""

    def __init__(self) -> None:
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora


class _Dependencia:
    """Dependencia externa simulada que cuenta sus invocaciones."""

    def __init__(self) -> None:
        self.llamadas = 0
        self.modo = "ok"  # "ok" | "falla" | "cuelga"

    async def __call__(self) -> str:
        self.llamadas += 1
        if self.modo == "falla":
            raise ConnectionError(f"proveedor caido para el usuario {_PII}")
        if self.modo == "cuelga":
            await asyncio.sleep(10)
        return "respuesta-real"


async def _respaldo() -> str:
    return "respuesta-de-respaldo"


@pytest.fixture
def reloj(monkeypatch: pytest.MonkeyPatch) -> _Reloj:
    # Se reemplaza solo la referencia `time` del módulo, no `time.monotonic`
    # global: el event loop de asyncio también lo usa y sus timeouts se congelarían.
    falso = _Reloj()
    monkeypatch.setattr(resilience, "time", SimpleNamespace(monotonic=falso))
    return falso


@pytest.fixture
def logs_json():
    """Captura lo que emite `cima.resilience` con el formateador JSON real."""
    salida = io.StringIO()
    handler = logging.StreamHandler(salida)
    handler.setFormatter(JsonFormatter())
    log = logging.getLogger("cima.resilience")
    nivel_previo = log.level
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    try:
        yield lambda: [json.loads(linea) for linea in salida.getvalue().splitlines()]
    finally:
        log.removeHandler(handler)
        log.setLevel(nivel_previo)
        set_correlation_id("")


def _breaker() -> CircuitBreaker:
    return CircuitBreaker("proveedor-x", failure_threshold=_UMBRAL, reset_seconds=_RESET)


async def _abrir(breaker: CircuitBreaker, dep: _Dependencia) -> None:
    dep.modo = "falla"
    for _ in range(_UMBRAL):
        with pytest.raises(DependenciaFallidaError):
            await breaker.llamar(dep)
    assert breaker.estado is EstadoCircuito.ABIERTO


# --------------------------------------------------------------------------- #
# Circuito cerrado
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_cerrado_la_llamada_pasa_y_devuelve_el_resultado(reloj: _Reloj) -> None:
    breaker, dep = _breaker(), _Dependencia()
    assert await breaker.llamar(dep) == "respuesta-real"
    assert dep.llamadas == 1
    assert breaker.estado is EstadoCircuito.CERRADO


@pytest.mark.asyncio
async def test_fallos_por_debajo_del_umbral_no_abren_y_un_exito_reinicia_la_cuenta(reloj: _Reloj) -> None:
    breaker, dep = _breaker(), _Dependencia()
    dep.modo = "falla"
    for _ in range(_UMBRAL - 1):
        with pytest.raises(DependenciaFallidaError):
            await breaker.llamar(dep)
    assert breaker.estado is EstadoCircuito.CERRADO

    dep.modo = "ok"
    await breaker.llamar(dep)
    # Tras el éxito hacen falta otra vez `_UMBRAL` fallos consecutivos.
    dep.modo = "falla"
    for _ in range(_UMBRAL - 1):
        with pytest.raises(DependenciaFallidaError):
            await breaker.llamar(dep)
    assert breaker.estado is EstadoCircuito.CERRADO


@pytest.mark.asyncio
async def test_fallo_con_fallback_devuelve_el_respaldo(reloj: _Reloj) -> None:
    breaker, dep = _breaker(), _Dependencia()
    dep.modo = "falla"
    assert await breaker.llamar(dep, fallback=_respaldo) == "respuesta-de-respaldo"
    assert dep.llamadas == 1


# --------------------------------------------------------------------------- #
# Timeout
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_dependencia_que_se_cuelga_corta_por_timeout_y_cuenta_como_fallo(reloj: _Reloj) -> None:
    breaker, dep = _breaker(), _Dependencia()
    dep.modo = "cuelga"
    with pytest.raises(DependenciaFallidaError, match="timeout"):
        await breaker.llamar(dep, timeout=0.05)

    assert await breaker.llamar(dep, timeout=0.05, fallback=_respaldo) == "respuesta-de-respaldo"
    await breaker.llamar(dep, timeout=0.05, fallback=_respaldo)
    assert breaker.estado is EstadoCircuito.ABIERTO


# --------------------------------------------------------------------------- #
# Circuito abierto
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_abierto_rechaza_sin_invocar_la_dependencia(reloj: _Reloj) -> None:
    breaker, dep = _breaker(), _Dependencia()
    await _abrir(breaker, dep)
    invocaciones = dep.llamadas

    dep.modo = "ok"
    with pytest.raises(CircuitoAbiertoError):
        await breaker.llamar(dep)
    assert await breaker.llamar(dep, fallback=_respaldo) == "respuesta-de-respaldo"
    assert dep.llamadas == invocaciones


@pytest.mark.asyncio
async def test_sigue_abierto_hasta_cumplir_el_tiempo_de_reinicio(reloj: _Reloj) -> None:
    breaker, dep = _breaker(), _Dependencia()
    await _abrir(breaker, dep)
    reloj.ahora += _RESET - 0.1
    assert breaker.estado is EstadoCircuito.ABIERTO
    reloj.ahora += 0.1
    assert breaker.estado is EstadoCircuito.SEMIABIERTO


# --------------------------------------------------------------------------- #
# Semiabierto
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_semiabierto_un_exito_cierra_el_circuito(reloj: _Reloj) -> None:
    breaker, dep = _breaker(), _Dependencia()
    await _abrir(breaker, dep)
    reloj.ahora += _RESET

    dep.modo = "ok"
    assert await breaker.llamar(dep) == "respuesta-real"
    assert breaker.estado is EstadoCircuito.CERRADO


@pytest.mark.asyncio
async def test_semiabierto_un_fallo_reabre_de_inmediato(reloj: _Reloj) -> None:
    breaker, dep = _breaker(), _Dependencia()
    await _abrir(breaker, dep)
    reloj.ahora += _RESET

    with pytest.raises(DependenciaFallidaError):
        await breaker.llamar(dep)
    assert breaker.estado is EstadoCircuito.ABIERTO
    # Y vuelve a esperar un periodo completo de reinicio.
    reloj.ahora += _RESET - 0.1
    assert breaker.estado is EstadoCircuito.ABIERTO


@pytest.mark.asyncio
async def test_semiabierto_deja_pasar_una_sola_llamada_de_prueba(reloj: _Reloj) -> None:
    """Con llamadas concurrentes, solo una prueba la dependencia; el resto usa el respaldo."""
    breaker, dep = _breaker(), _Dependencia()
    await _abrir(breaker, dep)
    reloj.ahora += _RESET
    invocaciones = dep.llamadas

    liberar = asyncio.Event()

    async def lenta() -> str:
        dep.llamadas += 1
        await liberar.wait()
        return "respuesta-real"

    tareas = [asyncio.create_task(breaker.llamar(lenta, timeout=5, fallback=_respaldo)) for _ in range(5)]
    await asyncio.sleep(0)
    liberar.set()
    resultados = await asyncio.gather(*tareas)

    assert dep.llamadas - invocaciones == 1
    assert sorted(resultados) == ["respuesta-de-respaldo"] * 4 + ["respuesta-real"]
    assert breaker.estado is EstadoCircuito.CERRADO


@pytest.mark.asyncio
async def test_semiabierto_si_la_prueba_se_cancela_se_permite_otra(reloj: _Reloj) -> None:
    breaker, dep = _breaker(), _Dependencia()
    await _abrir(breaker, dep)
    reloj.ahora += _RESET

    dep.modo = "cuelga"
    prueba = asyncio.create_task(breaker.llamar(dep, timeout=5))
    await asyncio.sleep(0)
    prueba.cancel()
    with pytest.raises(asyncio.CancelledError):
        await prueba

    dep.modo = "ok"
    assert await breaker.llamar(dep) == "respuesta-real"
    assert breaker.estado is EstadoCircuito.CERRADO


# --------------------------------------------------------------------------- #
# Registro: Correlation-ID y sin PII
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_activacion_se_registra_con_correlation_id_y_sin_pii(reloj: _Reloj, logs_json) -> None:
    set_correlation_id("cb-prueba-1")
    breaker, dep = _breaker(), _Dependencia()
    await _abrir(breaker, dep)
    await breaker.llamar(dep, fallback=_respaldo)

    eventos = logs_json()
    mensajes = [e["message"] for e in eventos]
    assert mensajes.count("dependencia_fallo") == _UMBRAL
    assert mensajes.count("circuito_abierto") == 1
    assert mensajes.count("circuito_rechazo") == 1

    abierto = next(e for e in eventos if e["message"] == "circuito_abierto")
    assert abierto["dependencia"] == "proveedor-x"
    assert abierto["fallos"] == _UMBRAL
    assert all(e["correlation_id"] == "cb-prueba-1" for e in eventos)
    fallo = next(e for e in eventos if e["message"] == "dependencia_fallo")
    assert fallo["motivo"] == "ConnectionError"
    # El mensaje de la excepción del proveedor (con PII) no llega a los logs.
    assert _PII not in json.dumps(eventos)


@pytest.mark.asyncio
async def test_el_error_de_dominio_no_expone_el_mensaje_del_proveedor(reloj: _Reloj) -> None:
    breaker, dep = _breaker(), _Dependencia()
    dep.modo = "falla"
    with pytest.raises(DependenciaFallidaError) as error:
        await breaker.llamar(dep)
    assert _PII not in str(error.value)
    # La causa original se conserva encadenada para diagnóstico interno.
    assert isinstance(error.value.__cause__, ConnectionError)
