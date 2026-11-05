"""Constantes y utilidades de dominio del Certification Service.

Define los límites del código de verificación y su generación. El código es
alfanumérico de longitud fija dentro del rango permitido (16–64, Req 6.3) y se
genera con `secrets` para que sea impredecible (no adivinable).
Requisito: 6.3.
"""

from __future__ import annotations

import secrets
import string
from typing import Final

# Longitud del código de verificación: mínimo 16, máximo 64 caracteres (Req 6.3).
CODE_MIN_LENGTH: Final = 16
CODE_MAX_LENGTH: Final = 64

# Longitud fija usada al emitir (dentro del rango permitido).
CODE_LENGTH: Final = 32

# Alfabeto del código: letras y dígitos (alfanumérico, Req 6.3).
_CODE_ALPHABET: Final = string.ascii_uppercase + string.digits


def generate_verification_code(length: int = CODE_LENGTH) -> str:
    """Genera un código de verificación alfanumérico impredecible.

    Usa `secrets.choice` (CSPRNG) para que el código no sea adivinable. La
    longitud se acota al rango permitido [16, 64] (Req 6.3).

    :param length: longitud deseada del código; se recorta al rango válido.
    :return: código alfanumérico en mayúsculas y dígitos.
    """
    safe_length = max(CODE_MIN_LENGTH, min(length, CODE_MAX_LENGTH))
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(safe_length))
