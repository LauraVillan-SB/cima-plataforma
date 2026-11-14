"""Videos propios de las microcápsulas guardados en la carpeta de medios del backend.

Solo para dev/local: en stage/prod los videos deben ir a almacenamiento de objetos con
CDN (pendiente con TI). Defensa contra path traversal (OWASP A01):

- El nombre debe cumplir `MEDIA_FILE_PATTERN` (allowlist: minúsculas, dígitos, guiones y
  `.mp4`); nunca se acepta una ruta.
- La ruta final se canonicaliza con `resolve()` y debe quedar justo dentro de la carpeta
  configurada (también descarta enlaces simbólicos que apunten afuera).
- Debe ser un archivo regular existente.

Si algo falla se devuelve None y el endpoint responde 404 genérico, sin revelar rutas.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.common.config import get_settings
from app.learning.constants import MEDIA_FILE_PATTERN, MEDIA_URL_PREFIX

# `backend/` (este archivo está en backend/app/learning/).
_BACKEND = Path(__file__).resolve().parents[2]


def carpeta_medios() -> Path:
    """Carpeta configurada de medios; si es relativa, se toma desde `backend/`."""
    configurada = Path(get_settings().learning_media_dir)
    return configurada if configurada.is_absolute() else _BACKEND / configurada


def nombre_valido(nombre: str) -> bool:
    """Verdadero si el nombre cumple la allowlist de archivos de video."""
    return re.fullmatch(MEDIA_FILE_PATTERN, nombre) is not None


def url_de(nombre: str) -> str:
    """Dirección pública del video, armada por el backend con un prefijo fijo."""
    if not nombre_valido(nombre):
        raise ValueError("Nombre de archivo de video inválido.")
    return f"{MEDIA_URL_PREFIX}{nombre}"


def resolver_medio(nombre: str, carpeta: Path) -> Path | None:
    """Ruta del archivo si es seguro servirlo; None en cualquier otro caso."""
    if not nombre_valido(nombre):
        return None
    base = carpeta.resolve()
    ruta = (base / nombre).resolve()
    if ruta.parent != base or not ruta.is_file():
        return None
    return ruta
