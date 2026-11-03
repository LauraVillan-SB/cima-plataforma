"""Limitador de tasa en memoria con ventana deslizante (Req 9.7, 12.2).

Implementación ligera para controlar ráfagas de solicitudes por clave (p. ej.
un identificador de actor). Registra las marcas de tiempo recientes por clave y
rechaza cuando se supera el máximo permitido dentro de la ventana.

NOTA: el almacén es en memoria por proceso. Para escalado horizontal con
estado compartido entre instancias (Req 12.3) debe respaldarse en un almacén
distribuido (p. ej. Redis) en la Tarea 10.3; la interfaz pública no cambiaría.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    """Limita a `max_hits` eventos por `window_seconds` para cada clave.

    No lanza excepciones: expone `allow`, que devuelve `True` si el evento está
    dentro del límite (y lo contabiliza) o `False` si debe rechazarse. La
    decisión de cómo responder (p. ej. lanzar `RateLimitedError`) queda en el
    llamador, para mantener esta utilidad agnóstica del dominio.
    """

    def __init__(self, max_hits: int, window_seconds: float) -> None:
        if max_hits < 1:
            raise ValueError("max_hits debe ser >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds debe ser > 0")
        self._max_hits = max_hits
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        """Contabiliza un intento para `key` y decide si está dentro del límite.

        Args:
            key: Identificador del sujeto limitado (p. ej. id de actor).
            now: Marca de tiempo (monotónica o epoch); por defecto `time.monotonic()`.

        Returns:
            `True` si el intento está dentro del límite; `False` si lo excede.
        """
        current = time.monotonic() if now is None else now
        ventana = self._hits[key]

        # Descarta las marcas fuera de la ventana deslizante.
        limite_inferior = current - self._window
        while ventana and ventana[0] <= limite_inferior:
            ventana.popleft()

        if len(ventana) >= self._max_hits:
            return False

        ventana.append(current)
        return True

    def reset(self, key: str) -> None:
        """Limpia el conteo de una clave (p. ej. tras un acceso legítimo)."""
        self._hits.pop(key, None)
