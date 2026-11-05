"""Constantes de dominio del Assessment Service.

Define el umbral de aprobación por defecto, el máximo de reintentos, la duración
del enfriamiento tras agotarlos y los límites de puntaje. Estos valores fijan el
comportamiento de evaluación en el servidor (la lógica nunca vive en el cliente).
Requisitos: 7.3, 7.4, 7.5.
"""

from __future__ import annotations

from typing import Final

# Umbral de aprobación por defecto cuando la ruta no define uno propio (Req 7.3).
DEFAULT_PASS_THRESHOLD: Final = 70

# Rango válido del puntaje y del umbral (Req 7.2, 7.3).
MIN_SCORE: Final = 0
MAX_SCORE: Final = 100

# Máximo de intentos no aprobados antes del enfriamiento (Req 7.4).
MAX_ATTEMPTS: Final = 3

# Duración del enfriamiento tras agotar los intentos, en horas (Req 7.5).
COOLDOWN_HOURS: Final = 24
