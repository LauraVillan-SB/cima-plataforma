"""Resiliencia para dependencias externas: circuit breaker, timeout y fallback.

Envuelve invocaciones a dependencias externas (LLM, STT/TTS, y otras) con un
circuit breaker que corta rápido cuando una dependencia falla de forma repetida,
aplica un timeout bajo y permite un fallback documentado. La activación del
circuito se registra con el Correlation-ID y sin PII.

Requisitos: 11.5, 11.6. El control de SSRF de las URLs externas lo provee
`app/common/http_client.py`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import TypeVar

from app.common.config import get_settings
from app.common.logging import log_event

logger = logging.getLogger("cima.resilience")

T = TypeVar("T")


class EstadoCircuito(str, Enum):
    """Estados del circuit breaker."""

    CERRADO = "cerrado"      # Operación normal; las llamadas pasan.
    ABIERTO = "abierto"      # Cortado; las llamadas se rechazan de inmediato.
    SEMIABIERTO = "semiabierto"  # Prueba una llamada para decidir si cerrar.


class CircuitoAbiertoError(Exception):
    """El circuito está abierto: la llamada se rechaza sin invocar la dependencia."""


class DependenciaFallidaError(Exception):
    """La dependencia externa falló o excedió el timeout (envoltura uniforme)."""


class CircuitBreaker:
    """Circuit breaker simple por dependencia externa.

    Tras `failure_threshold` fallos consecutivos abre el circuito y rechaza las
    llamadas durante `reset_seconds`; luego pasa a semiabierto y prueba una
    llamada: si tiene éxito, cierra; si falla, vuelve a abrir.
    """

    def __init__(
        self,
        nombre: str,
        failure_threshold: int | None = None,
        reset_seconds: float | None = None,
    ) -> None:
        settings = get_settings()
        self._nombre = nombre
        self._umbral = failure_threshold or settings.circuit_failure_threshold
        self._reset = reset_seconds or settings.circuit_reset_seconds
        self._fallos = 0
        self._estado = EstadoCircuito.CERRADO
        self._abierto_desde = 0.0
        # En semiabierto solo pasa UNA llamada de prueba; las concurrentes se
        # rechazan como si el circuito siguiera abierto.
        self._prueba_en_curso = False

    @property
    def estado(self) -> EstadoCircuito:
        """Estado actual, reevaluando la transición a semiabierto por tiempo."""
        if (
            self._estado is EstadoCircuito.ABIERTO
            and (time.monotonic() - self._abierto_desde) >= self._reset
        ):
            self._estado = EstadoCircuito.SEMIABIERTO
        return self._estado

    def _al_exito(self) -> None:
        self._fallos = 0
        self._estado = EstadoCircuito.CERRADO

    def _al_fallo(self) -> None:
        self._fallos += 1
        if self._fallos >= self._umbral or self._estado is EstadoCircuito.SEMIABIERTO:
            self._estado = EstadoCircuito.ABIERTO
            self._abierto_desde = time.monotonic()
            # Registro sin PII: solo el nombre de la dependencia y el conteo.
            log_event(
                logger,
                "circuito_abierto",
                dependencia=self._nombre,
                fallos=self._fallos,
            )

    async def llamar(
        self,
        operacion: Callable[[], Awaitable[T]],
        *,
        timeout: float | None = None,
        fallback: Callable[[], Awaitable[T]] | None = None,
    ) -> T:
        """Ejecuta `operacion` con timeout y protección de circuito.

        Si el circuito está abierto o la operación falla/excede el timeout, usa
        `fallback` cuando se provee; de lo contrario lanza un error de dominio.
        El fallback es la respuesta de respaldo documentada (Req 11.6).
        """
        settings = get_settings()
        limite = timeout if timeout is not None else settings.http_timeout_seconds

        estado = self.estado
        if estado is EstadoCircuito.ABIERTO or (
            estado is EstadoCircuito.SEMIABIERTO and self._prueba_en_curso
        ):
            log_event(logger, "circuito_rechazo", dependencia=self._nombre)
            if fallback is not None:
                return await fallback()
            raise CircuitoAbiertoError(f"circuito abierto: {self._nombre}")

        # Sin `await` entre la comprobación y esta asignación: en un mismo event
        # loop ninguna otra llamada puede colarse como segunda prueba.
        es_prueba = estado is EstadoCircuito.SEMIABIERTO
        if es_prueba:
            self._prueba_en_curso = True
        try:
            resultado = await asyncio.wait_for(operacion(), timeout=limite)
        except asyncio.TimeoutError as exc:
            return await self._manejar_fallo("timeout", fallback, exc)
        except Exception as exc:
            # Un circuit breaker debe contabilizar CUALQUIER fallo de la
            # dependencia externa para poder abrirse; por eso se captura amplio
            # de forma deliberada. El detalle se registra sin PII y el error se
            # reenvía envuelto en un tipo de dominio específico, no se silencia.
            return await self._manejar_fallo(type(exc).__name__, fallback, exc)
        else:
            self._al_exito()
            return resultado
        finally:
            # También si la prueba se cancela: así otra llamada puede probar.
            if es_prueba:
                self._prueba_en_curso = False

    async def _manejar_fallo(
        self,
        motivo: str,
        fallback: Callable[[], Awaitable[T]] | None,
        exc: BaseException,
    ) -> T:
        """Contabiliza el fallo, registra sin PII y aplica fallback o relanza."""
        self._al_fallo()
        log_event(
            logger,
            "dependencia_fallo",
            dependencia=self._nombre,
            motivo=motivo,
        )
        if fallback is not None:
            return await fallback()
        raise DependenciaFallidaError(
            f"dependencia {self._nombre} fallo: {motivo}"
        ) from exc
