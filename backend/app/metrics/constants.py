"""Constantes de dominio del Metrics Service.

Define la allowlist de tipos de evento de métrica, el marcador de zona no
clasificada y el umbral de k-anonimato para la supresión en reportes agregados.
El enfoque de allowlist (sobre blocklist) es un requisito de seguridad:
cualquier tipo de evento fuera de esta lista se rechaza.
Requisitos: 8.1, 8.2, 8.6.
"""

from __future__ import annotations

# Allowlist de tipos de evento de métrica aceptados (Req 8.1).
ALLOWED_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "microcapsula_completada",
        "ruta_completada",
        "conversion_microseguro",
    }
)

# Marcador para eventos sin zona geográfica; se registran como no clasificados (Req 8.2).
UNCLASSIFIED_ZONE = "sin_zona"

# Longitud máxima de la zona geográfica (consistente con el Perfil).
GEO_ZONE_MAX_LENGTH = 100

# Umbral de k-anonimato: se suprimen zonas con menos de este número de
# Usuarios distintos para evitar la reidentificación (Req 8.6, 15.4).
K_ANONYMITY_THRESHOLD = 5
