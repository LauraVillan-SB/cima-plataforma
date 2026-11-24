"""Deja listos los dos usuarios de prueba del ambiente local (idempotente).

Uso (desde `backend/`, con la base migrada y el catálogo cargado):

    $env:CIMA_CLAVE_DEMO = "<4 dígitos>"
    poetry run python -m app.dev.usuarios_locales

Crea o actualiza dos Perfiles ficticios para recorrer la PWA:

- Patricia: agricultora de café en el Huila.
- Rosa Ruiz: tendera de barrio en Bogotá (pyme), que ve la ruta de la plata digital.

Los nombres NO se guardan en el servidor: el Perfil solo tiene teléfono, actividad y
zona (Req 9.1). Para que la app salude "Hola, doña Rosa", el nombre se escribe en
"Mi perfil" y queda solo en el celular (ver `frontend/src/app/core/trato.ts`).

La Clave se lee de `CIMA_CLAVE_DEMO` (nunca del código) y se guarda solo como hash,
igual que en el registro (Req 1.5). Si el Perfil ya existe, se le vuelven a poner la
Clave, la actividad y la zona, y se le quita cualquier bloqueo por intentos fallidos.
Nunca borra datos. Se niega a correr fuera de los entornos de desarrollo y pruebas.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.password import hash_clave
from app.common.config import get_settings
from app.common.database import async_session_factory
from app.common.logging import log_event
from app.common.masking import mask_value
from app.profile.constants import ALLOWED_ACTIVITY_TYPES
from app.profile.models import Profile

logger = logging.getLogger("cima.dev.usuarios_locales")

# Solo en local y pruebas; nunca en stage ni producción.
ALLOWED_ENVIRONMENTS = frozenset({"dev", "local", "test"})

# Variable de entorno con la Clave de los usuarios de prueba (4 dígitos).
VARIABLE_CLAVE = "CIMA_CLAVE_DEMO"
_CLAVE_VALIDA = re.compile(r"^\d{4}$")


@dataclass(frozen=True)
class UsuarioLocal:
    """Usuario de prueba: el nombre es solo para mostrarlo en consola."""

    nombre: str
    telefono: str
    actividad: str
    zona: str


# Teléfonos ficticios, reservados para el ambiente local.
USUARIOS: tuple[UsuarioLocal, ...] = (
    UsuarioLocal("Patricia", "3000000001", "cafe", "Huila"),
    UsuarioLocal("Rosa Ruiz", "3000000002", "tienda_barrio", "Bogotá D.C."),
)


@dataclass(frozen=True)
class Resultado:
    """Qué pasó con cada usuario."""

    nombre: str
    telefono_enmascarado: str
    actividad: str
    creado: bool


async def asegurar_usuario(db: AsyncSession, usuario: UsuarioLocal, clave: str) -> Resultado:
    """Crea el Perfil o lo actualiza para que quede listo para entrar.

    Raises:
        ValueError: si la actividad no está en la allowlist del Perfil.
    """
    if usuario.actividad not in ALLOWED_ACTIVITY_TYPES:
        raise ValueError(f"Actividad no permitida: {usuario.actividad}")
    perfil = await db.scalar(select(Profile).where(Profile.phone_e164 == usuario.telefono))
    creado = perfil is None
    if perfil is None:
        perfil = Profile(phone_e164=usuario.telefono)
        db.add(perfil)
    perfil.clave_hash = hash_clave(clave)
    perfil.activity_type = usuario.actividad
    perfil.geo_zone = usuario.zona
    perfil.failed_attempts = 0
    perfil.locked_until = None
    await db.flush()
    log_event(logger, "dev_usuario_local_listo", profile_id=str(perfil.id), creado=creado)
    return Resultado(usuario.nombre, mask_value(usuario.telefono), usuario.actividad, creado)


async def asegurar_usuarios(db: AsyncSession, clave: str) -> list[Resultado]:
    """Deja listos todos los usuarios de prueba en una sola transacción."""
    resultados = [await asegurar_usuario(db, usuario, clave) for usuario in USUARIOS]
    await db.commit()
    return resultados


async def _run(clave: str) -> list[Resultado]:
    async with async_session_factory() as db:
        return await asegurar_usuarios(db, clave)


def main() -> int:
    """Punto de entrada de línea de comandos. Devuelve el código de salida."""
    entorno = get_settings().app_env.lower()
    if entorno not in ALLOWED_ENVIRONMENTS:
        print(f"No se crean usuarios de prueba en el entorno '{entorno}'.")
        return 1
    clave = os.environ.get(VARIABLE_CLAVE, "")
    if not _CLAVE_VALIDA.fullmatch(clave):
        print(f"Defina {VARIABLE_CLAVE} con una Clave de 4 dígitos antes de ejecutar.")
        return 1
    for r in asyncio.run(_run(clave)):
        accion = "creado" if r.creado else "actualizado"
        print(f"{r.nombre}: celular {r.telefono_enmascarado}, {r.actividad} ({accion}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
