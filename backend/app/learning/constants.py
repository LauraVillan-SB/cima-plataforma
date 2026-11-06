"""Constantes de dominio del Learning Service.

Define la allowlist de temas de las microcápsulas, el tema general de respaldo y
los límites de selección, duración y solicitudes de perfil. El enfoque de
allowlist (sobre blocklist) es un requisito de seguridad: cualquier valor fuera
de estas listas se rechaza.
Requisitos: 4.1, 4.2, 4.3, 4.4, 4.8, 4.9.
"""

from __future__ import annotations

from typing import Final

# Temas en los que se clasifica cada microcápsula; exactamente uno (Req 4.2).
TOPIC_GESTION_RIESGOS: Final = "gestion_riesgos"
TOPIC_FINANZAS: Final = "finanzas"
TOPIC_ADAPTACION_CLIMA: Final = "adaptacion_clima"

ALLOWED_TOPICS: Final[frozenset[str]] = frozenset(
    {TOPIC_GESTION_RIESGOS, TOPIC_FINANZAS, TOPIC_ADAPTACION_CLIMA}
)

# Tema general de respaldo cuando no hay microcápsulas para la actividad del
# Perfil o el perfil está incompleto tras agotar las solicitudes (Req 4.4, 4.9).
FALLBACK_TOPIC: Final = TOPIC_ADAPTACION_CLIMA

# Duración de contenido de una microcápsula en segundos: 3–5 min, inclusive (Req 4.1).
MIN_DURATION_SEC: Final = 180
MAX_DURATION_SEC: Final = 300

# Cantidad de microcápsulas por selección personalizada: entre 1 y 10 (Req 4.3).
MAX_SELECTION: Final = 10

# Máximo de solicitudes al Usuario de su tipo de cultivo/comercio antes de
# entregar el tema general sin personalización (Req 4.8, 4.9).
MAX_PROFILE_PROMPTS: Final = 3

# Factor sobre la duración esperada de la microcápsula a partir del cual se
# considera que el Usuario excedió el tiempo esperado (Req 17.1). Valor de
# referencia pendiente de validación por negocio.
EXPECTED_TIME_FACTOR: Final = 2

# Valores del ritmo que el backend indica al cliente para la microcápsula siguiente.
PACE_STANDARD: Final = "standard"
PACE_SLOW: Final = "slow"

# Tope del tiempo reportado por el cliente al finalizar una cápsula (24 h). Acota la
# entrada: un valor mayor no es una medición creíble y se rechaza (validación).
MAX_ELAPSED_SEC: Final = 86400

# Reintentos del registro de un evento antes de conservarlo para registro posterior
# (Req 4.7, Property 15): nunca más de 3 reintentos tras el primer intento.
MAX_EVENT_RETRIES: Final = 3

# Eventos pendientes que se reintentan por invocación de `drain_outbox`.
MAX_DRAIN_BATCH: Final = 50
