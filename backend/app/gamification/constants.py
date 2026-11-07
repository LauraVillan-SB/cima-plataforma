"""Constantes de dominio del Gamification Service.

Define las reglas de otorgamiento de reconocimientos (Insignia + puntos) por
tipo de logro. Las reglas viven solo en el backend: el cliente nunca decide qué
se otorga ni cuántos puntos vale (Req 19.3). Cada logro (`trigger`) está en una
allowlist; cualquier otro se rechaza.

El catálogo es contenido de referencia pendiente de validación por negocio. Los
puntos de cada Insignia se suman al total del Perfil solo la primera vez que la
Insignia se otorga (Req 19.5). CIMA no aplica descuentos ni beneficios sobre
Microseguros porque no emite pólizas (alcance del proyecto).
Requisitos: 19.1, 19.3, 19.5.
"""

from __future__ import annotations

from dataclasses import dataclass

# Logros que disparan un reconocimiento (coinciden con los eventos de métrica).
TRIGGER_MICROCAPSULA_COMPLETADA = "microcapsula_completada"
TRIGGER_RUTA_COMPLETADA = "ruta_completada"

# Intentos máximos de otorgamiento ante conflictos de concurrencia (Req 19.6).
MAX_GRANT_ATTEMPTS = 3


@dataclass(frozen=True)
class BadgeRule:
    """Regla de otorgamiento: la Insignia y los puntos que vale un logro."""

    code: str
    name: str
    points: int


# Regla por logro. Una Insignia por logro; sus puntos se suman una sola vez.
RECOGNITION_RULES: dict[str, BadgeRule] = {
    TRIGGER_MICROCAPSULA_COMPLETADA: BadgeRule(
        code="primer_paso", name="Primer paso", points=10
    ),
    TRIGGER_RUTA_COMPLETADA: BadgeRule(
        code="ruta_completada", name="Ruta completada", points=50
    ),
}

# Nombre legible por código de Insignia, derivado del catálogo (una sola fuente
# de verdad). Se usa al listar los reconocimientos de un Perfil (Req 19.7).
BADGE_NAMES: dict[str, str] = {rule.code: rule.name for rule in RECOGNITION_RULES.values()}


# --------------------------------------------------------------------------- #
# Niveles, racha y ranking
#
# Extensión de experiencia de usuario NO especificada en requirements.md: el
# requisito 19 solo exige puntos e Insignias. Niveles, racha y ranking se derivan
# de datos que ya tiene el backend (puntos y actividad), sin inventar métricas que
# no se puedan respaldar. Las reglas viven solo en el backend (Req 19.3).
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Level:
    """Nivel de progreso: umbral mínimo de puntos y nombre legible."""

    number: int
    name: str
    min_points: int


# Niveles por puntos acumulados, de menor a mayor. Valores de referencia
# pendientes de validación por negocio.
LEVELS: tuple[Level, ...] = (
    Level(1, "Primeros pasos", 0),
    Level(2, "Aprendiz", 50),
    Level(3, "Conocedor", 150),
    Level(4, "Explorador financiero", 300),
    Level(5, "Experto CIMA", 600),
)

# Ventana para que un día cuente como continuación de la racha: si la última
# actividad fue ayer u hoy, la racha sigue; si pasó más de un día, se reinicia.
STREAK_RESET_DAYS: Final = 1

# Tamaño por defecto del ranking (top N). Acota la respuesta.
DEFAULT_LEADERBOARD_SIZE: Final = 10
MAX_LEADERBOARD_SIZE: Final = 50
