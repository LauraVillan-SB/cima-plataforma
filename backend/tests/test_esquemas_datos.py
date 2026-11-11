"""Pruebas unitarias de los esquemas de datos (Tarea 4.3).

Verifican restricciones, tipos y defaults del esquema sin una base real:

- sobre `Base.metadata` (los modelos), que el checkpoint 5 confirmó idénticos a
  las migraciones con `alembic check`;
- sobre el DDL que generan las migraciones en modo offline, para lo que
  `alembic check` no compara: los defaults del lado del servidor (p. ej. el
  `pass_threshold` default 70, Req 7.3);
- que cada valor de una allowlist o rango del dominio quepa en el ancho de su
  columna. Si no cabe, la inserción falla en Postgres con un 500; así pasó con
  el Correlation-ID (hasta 128 caracteres) en `ai_interactions.correlation_id`
  (VARCHAR(64)).

Las validaciones de rango de los DTOs ya tienen sus pruebas de propiedad
(Properties 10, 11 y 43) y no se repiten aquí.

Validates: Requirements 4.1, 4.2, 7.3
"""

from __future__ import annotations

import importlib
import io

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Boolean, Integer, String, Table, UniqueConstraint, Uuid

from app.chat import constants as chat_constants
from app.common.correlation import CORRELATION_ID_MAX_LENGTH
from app.common.database import Base
from app.certification.constants import CODE_MAX_LENGTH
from app.learning.constants import ALLOWED_TOPICS
from app.profile.constants import ALLOWED_ACTIVITY_TYPES, GEO_ZONE_MAX_LENGTH, PHONE_MAX_DIGITS
from app.profile.models import ROLE_ADMIN, ROLE_USUARIO

# Los mismos dominios que importa `alembic/env.py` para poblar el metadata.
_DOMINIOS = (
    "profile", "metrics", "conversion", "gamification", "chat",
    "learning", "assessment", "certification", "survey", "sync",
)
for _dominio in _DOMINIOS:
    importlib.import_module(f"app.{_dominio}.models")


def _tabla(nombre: str) -> Table:
    return Base.metadata.tables[nombre]


def _conjuntos_unicos(tabla: Table) -> set[tuple[str, ...]]:
    """Columnas con unicidad, por restricción UNIQUE o por índice único."""
    unicos = {
        tuple(c.name for c in r.columns)
        for r in tabla.constraints
        if isinstance(r, UniqueConstraint)
    }
    unicos |= {tuple(c.name for c in i.columns) for i in tabla.indexes if i.unique}
    return unicos


def _default_orm(tabla: str, columna: str) -> object:
    default = _tabla(tabla).c[columna].default
    assert default is not None, f"{tabla}.{columna} no tiene default"
    return default.arg


@pytest.fixture(scope="module")
def ddl() -> str:
    """SQL de `alembic upgrade head` en modo offline, sin conectarse a la base.

    El `Config` se crea sin archivo `.ini` a propósito: `env.py` solo llama a
    `fileConfig` cuando hay archivo, y esa llamada deshabilitaría los loggers ya
    creados, rompiendo la captura de logs de otras pruebas de la suite.
    """
    salida = io.StringIO()
    config = Config(output_buffer=salida)
    config.set_main_option("script_location", "alembic")
    command.upgrade(config, "head", sql=True)
    return salida.getvalue()


# --------------------------------------------------------------------------- #
# Umbral de aprobación (Req 7.3): entero, obligatorio, default 70
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("tabla", ["learning_paths", "assessments"])
def test_pass_threshold_es_entero_obligatorio_con_default_70(tabla: str) -> None:
    columna = _tabla(tabla).c["pass_threshold"]
    assert isinstance(columna.type, Integer)
    assert columna.nullable is False
    assert _default_orm(tabla, "pass_threshold") == 70


def test_migraciones_fijan_pass_threshold_default_70_en_la_base(ddl: str) -> None:
    """Un INSERT que no envíe el umbral también obtiene 70, no solo el ORM."""
    assert ddl.count("pass_threshold INTEGER DEFAULT '70' NOT NULL") == 2


# --------------------------------------------------------------------------- #
# Microcápsulas (Req 4.1, 4.2)
# --------------------------------------------------------------------------- #
def test_microcapsula_tema_y_duracion_son_obligatorios() -> None:
    tabla = _tabla("microcapsules")
    assert isinstance(tabla.c["duration_sec"].type, Integer)
    assert tabla.c["duration_sec"].nullable is False
    assert isinstance(tabla.c["topic"].type, String)
    assert tabla.c["topic"].nullable is False


def test_todo_tema_permitido_cabe_en_la_columna() -> None:
    ancho = _tabla("microcapsules").c["topic"].type.length
    assert max(len(t) for t in ALLOWED_TOPICS) <= ancho


# --------------------------------------------------------------------------- #
# Perfil (Req 1.5, 9.1)
# --------------------------------------------------------------------------- #
def test_perfil_campos_obligatorios_y_defaults() -> None:
    tabla = _tabla("profiles")
    for nombre in ("phone_e164", "clave_hash", "activity_type", "geo_zone", "role"):
        assert tabla.c[nombre].nullable is False, nombre
    assert _default_orm("profiles", "role") == ROLE_USUARIO
    assert _default_orm("profiles", "failed_attempts") == 0


def test_perfil_valores_del_dominio_caben_en_sus_columnas() -> None:
    tabla = _tabla("profiles")
    # E.164: "+" y hasta 15 dígitos.
    assert 1 + PHONE_MAX_DIGITS <= tabla.c["phone_e164"].type.length
    assert max(len(a) for a in ALLOWED_ACTIVITY_TYPES) <= tabla.c["activity_type"].type.length
    assert GEO_ZONE_MAX_LENGTH <= tabla.c["geo_zone"].type.length
    assert max(len(ROLE_USUARIO), len(ROLE_ADMIN)) <= tabla.c["role"].type.length


# --------------------------------------------------------------------------- #
# Unicidad e idempotencia (Req 6.4, 8.2, 18.2, 19.5, 20.6)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("tabla", "columnas"),
    [
        ("profiles", ("phone_e164",)),
        ("assessments", ("path_id",)),
        ("certificates", ("profile_id", "path_id")),
        ("certificates", ("verification_code",)),
        ("incentives", ("profile_id", "path_id")),
        ("path_progress", ("profile_id", "path_id")),
        ("survey_responses", ("profile_id", "path_id")),
        ("sync_path_progress", ("profile_id", "path_id")),
        ("user_badges", ("profile_id", "badge_code")),
        ("user_points", ("profile_id",)),
    ],
)
def test_restricciones_de_unicidad(tabla: str, columnas: tuple[str, ...]) -> None:
    assert columnas in _conjuntos_unicos(_tabla(tabla))


@pytest.mark.parametrize(
    "tabla",
    ["metric_events", "conversion_intents", "user_badges", "survey_responses", "sync_actions"],
)
def test_client_event_id_es_uuid_unico_y_obligatorio(tabla: str) -> None:
    columna = _tabla(tabla).c["client_event_id"]
    assert isinstance(columna.type, Uuid)
    assert columna.nullable is False
    assert ("client_event_id",) in _conjuntos_unicos(_tabla(tabla))


def test_codigo_de_certificado_cabe_en_la_columna() -> None:
    """Req 6.3: el código verificable mide entre 16 y 64 caracteres."""
    assert CODE_MAX_LENGTH <= _tabla("certificates").c["verification_code"].type.length


# --------------------------------------------------------------------------- #
# Encuesta y progreso
# --------------------------------------------------------------------------- #
def test_calificacion_de_encuesta_es_entero_obligatorio() -> None:
    columna = _tabla("survey_responses").c["rating"]
    assert isinstance(columna.type, Integer)
    assert columna.nullable is False


@pytest.mark.parametrize(
    ("tabla", "columna", "esperado"),
    [
        ("path_progress", "completed", False),
        ("path_progress", "last_completed_step", 0),
        ("user_points", "total_points", 0),
    ],
)
def test_defaults_de_progreso_y_puntos(tabla: str, columna: str, esperado: object) -> None:
    assert _default_orm(tabla, columna) == esperado
    if isinstance(esperado, bool):
        assert isinstance(_tabla(tabla).c[columna].type, Boolean)


# --------------------------------------------------------------------------- #
# Chat: estados, decisiones del guardrail y Correlation-ID
# --------------------------------------------------------------------------- #
def _valores(prefijo: str) -> set[str]:
    return {
        valor
        for nombre, valor in vars(chat_constants).items()
        if nombre.startswith(prefijo) and isinstance(valor, str)
    }


def test_estados_y_decisiones_del_chat_caben_en_sus_columnas() -> None:
    tabla = _tabla("ai_interactions")
    assert _default_orm("ai_interactions", "status") == chat_constants.ESTADO_ENCOLADO
    assert max(len(v) for v in _valores("ESTADO_")) <= tabla.c["status"].type.length
    assert max(len(v) for v in _valores("GUARDRAIL_")) <= tabla.c["guardrail_decision"].type.length


def test_todo_correlation_id_admitido_cabe_en_la_columna() -> None:
    """Regresión: un id válido de 65–128 caracteres daba 500 al guardar un mensaje."""
    ancho = _tabla("ai_interactions").c["correlation_id"].type.length
    assert CORRELATION_ID_MAX_LENGTH <= ancho
