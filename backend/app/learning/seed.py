"""Carga idempotente del catálogo de contenido del Learning Service.

Uso (desde `backend/`, con la base migrada):

    poetry run python -m app.learning.seed

Inserta o actualiza microcápsulas, rutas y evaluaciones definidas en `catalog.py`. Los
identificadores son deterministas (`uuid5` del `slug`), así que ejecutarlo varias veces
actualiza las mismas filas y no duplica nada ni toca el progreso de los Usuarios. Nunca
borra datos. Se niega a correr fuera de los entornos de desarrollo y pruebas: el
contenido de producción pasa por revisión de la Escuela de Sostenibilidad e Inclusión.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.assessment.models import Assessment
from app.common.config import get_settings
from app.common.database import async_session_factory
from app.common.logging import log_event
from app.learning.catalog import CAPSULES, PATHS, CapsuleSpec, PathSpec
from app.learning.models import LearningPath, Microcapsule

logger = logging.getLogger("cima.learning.seed")

# Entornos donde se permite cargar el catálogo de ejemplo.
ALLOWED_ENVIRONMENTS = frozenset({"dev", "local", "test", "stage"})


@dataclass(frozen=True)
class SeedResult:
    """Cuántas filas se insertaron o actualizaron."""

    capsules: int
    paths: int
    assessments: int


def _capsule_values(spec: CapsuleSpec) -> dict[str, object]:
    """Columnas de una microcápsula a partir de su definición."""
    video = spec.video
    return {
        "topic": spec.topic,
        "activity_tags": list(spec.tags),
        "duration_sec": spec.duration_sec,
        "relevance": Decimal(str(spec.relevance)),
        "difficulty": 0,
        "title": spec.title,
        "summary": spec.summary,
        "paragraphs": list(spec.paragraphs),
        "key_points": list(spec.key_points),
        "video_id": video.video_id if video else None,
        "video_title": video.title if video else None,
        "video_channel": video.channel if video else None,
        "video_file": spec.video_file,
    }


async def _upsert_capsule(db: AsyncSession, spec: CapsuleSpec) -> None:
    """Inserta la microcápsula o actualiza su contenido si ya existe."""
    values = _capsule_values(spec)
    stmt = pg_insert(Microcapsule).values(id=spec.id, **values)
    await db.execute(
        stmt.on_conflict_do_update(index_elements=[Microcapsule.id], set_=values)
    )


async def _upsert_path(db: AsyncSession, spec: PathSpec) -> None:
    """Inserta la ruta o actualiza su secuencia de cápsulas si ya existe."""
    ids_by_slug = {capsule.slug: capsule.id for capsule in CAPSULES}
    values = {
        "microcapsule_ids": [ids_by_slug[slug] for slug in spec.capsule_slugs],
        "pass_threshold": spec.pass_threshold,
        "title": spec.title,
        "summary": spec.summary,
    }
    stmt = pg_insert(LearningPath).values(id=spec.id, **values)
    await db.execute(
        stmt.on_conflict_do_update(index_elements=[LearningPath.id], set_=values)
    )


async def _upsert_assessment(db: AsyncSession, spec: PathSpec) -> None:
    """Inserta la evaluación de la ruta o actualiza sus preguntas si ya existe."""
    questions = [
        {
            "id": index,
            "prompt": question.prompt,
            "options": list(question.options),
            "correct": question.correct,
        }
        for index, question in enumerate(spec.questions)
    ]
    values = {"questions": questions, "pass_threshold": spec.pass_threshold}
    stmt = pg_insert(Assessment).values(path_id=spec.id, **values)
    await db.execute(
        stmt.on_conflict_do_update(index_elements=[Assessment.path_id], set_=values)
    )


async def seed_catalog(db: AsyncSession) -> SeedResult:
    """Carga el catálogo completo en una sola transacción.

    Args:
        db: sesión de base de datos.

    Returns:
        Cuántas microcápsulas, rutas y evaluaciones se procesaron.
    """
    for capsule in CAPSULES:
        await _upsert_capsule(db, capsule)
    for path in PATHS:
        await _upsert_path(db, path)
        await _upsert_assessment(db, path)
    await db.commit()
    log_event(
        logger,
        "learning_catalog_seeded",
        capsules=len(CAPSULES),
        paths=len(PATHS),
    )
    return SeedResult(capsules=len(CAPSULES), paths=len(PATHS), assessments=len(PATHS))


async def _run() -> SeedResult:
    """Abre una sesión y carga el catálogo."""
    async with async_session_factory() as db:
        return await seed_catalog(db)


def main() -> int:
    """Punto de entrada de línea de comandos. Devuelve el código de salida."""
    environment = get_settings().app_env.lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        print(f"No se carga el catálogo de ejemplo en el entorno '{environment}'.")
        return 1
    result = asyncio.run(_run())
    print(
        f"Catálogo cargado: {result.capsules} microcápsulas, {result.paths} rutas, "
        f"{result.assessments} evaluaciones."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
