"""Constantes de dominio del Survey Service.

Define el rango permitido de la calificación (escala 1–5), el marcador de zona
no clasificada y el umbral de k-anonimato para la supresión en reportes
agregados, consistente con el Metrics Service.
Requisitos: 20.3, 20.5, 20.7.
"""

from __future__ import annotations

# Escala de calificación permitida para la Encuesta de Satisfacción (Req 20.3).
RATING_MIN = 1
RATING_MAX = 5

# Marcador para respuestas sin zona geográfica (consistente con Metrics).
UNCLASSIFIED_ZONE = "sin_zona"

# Longitud máxima de la zona geográfica (consistente con el resto del dominio).
GEO_ZONE_MAX_LENGTH = 100

# Umbral de k-anonimato: se suprimen zonas con menos de este número de
# Usuarios distintos para evitar la reidentificación (Req 20.7).
K_ANONYMITY_THRESHOLD = 5
