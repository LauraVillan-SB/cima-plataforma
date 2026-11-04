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
