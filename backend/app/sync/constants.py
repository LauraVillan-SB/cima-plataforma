"""Constantes de dominio del Offline Sync Service.

Define la allowlist de tipos de acción que la cola offline puede sincronizar y
el límite de tamaño de lote. El enfoque de allowlist (sobre blocklist) es un
requisito de seguridad: cualquier tipo de acción fuera de esta lista se rechaza.
Requisitos: 18.2, 18.4.
"""

from __future__ import annotations

# Allowlist de tipos de acción sincronizables desde la cola offline (Req 18.2).
ALLOWED_ACTION_TYPES: frozenset[str] = frozenset(
    {
        "microcapsula_finalizada",
        "evaluacion_respondida",
    }
)

# Tamaño máximo de un lote de sincronización para acotar el costo por request.
MAX_BATCH_SIZE = 100
