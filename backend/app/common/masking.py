"""Utilidades de enmascaramiento de PII (Habeas Data).

Deja visibles como máximo los últimos N caracteres de un valor sensible.
Se usa tanto en respuestas de API (DTOs) como en el logging estructurado.
Requisitos: 5.9, 9.4.
"""

from __future__ import annotations

DEFAULT_VISIBLE_CHARS = 4


def mask_value(value: str | None, visible: int = DEFAULT_VISIBLE_CHARS) -> str:
    """Enmascara un valor dejando visibles a lo sumo los últimos `visible` caracteres.

    Ejemplos:
        mask_value("3001234567") -> "******4567"
        mask_value("ab")          -> "ab"  (más corto que `visible`)
        mask_value(None)          -> ""

    Args:
        value: Valor sensible a enmascarar. `None` se trata como cadena vacía.
        visible: Cantidad de caracteres finales que permanecen visibles.

    Returns:
        El valor con los caracteres iniciales reemplazados por asteriscos.
    """
    safe = value or ""
    keep = max(0, min(visible, len(safe)))
    hidden = len(safe) - keep
    return ("*" * hidden) + safe[hidden:]
