"""Constantes de dominio del Perfil de Usuario.

Define la lista de valores permitidos (allowlist) para el tipo de cultivo o
comercio. El enfoque de allowlist (sobre blocklist) es un requisito de
seguridad: cualquier valor fuera de esta lista se rechaza.
Requisito: 9.2.
"""

from __future__ import annotations

# Allowlist de tipos de cultivo o comercio aceptados por el Perfil de Usuario.
ALLOWED_ACTIVITY_TYPES: frozenset[str] = frozenset(
    {
        "cafe",
        "platano",
        "aguacate",
        "cacao",
        "arroz",
        "maiz",
        "ganaderia",
        "hortalizas",
        "tienda_barrio",
        "panaderia",
        "miscelanea",
        "fruteria",
    }
)

# Límites de validación del Perfil (Req 9.2).
PHONE_MIN_DIGITS = 7
PHONE_MAX_DIGITS = 15
GEO_ZONE_MAX_LENGTH = 100
