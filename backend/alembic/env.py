"""Entorno de ejecución de Alembic para CIMA (modo asíncrono con asyncpg).

La URL de conexión se inyecta en runtime desde la configuración de la app
(variables de entorno / Secret Manager), nunca desde `alembic.ini`, para no
versionar credenciales. Se importan los modelos de los dominios existentes para
que `--autogenerate` detecte el esquema objetivo.
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.common.config import get_settings
from app.common.database import Base

# Importa los modelos para poblar Base.metadata (necesario para autogenerate).
# A medida que se creen modelos en otros dominios, se importan aquí.
from app.profile import models as _profile_models  # noqa: F401
from app.metrics import models as _metric_models  # noqa: F401
from app.conversion import models as _conversion_models  # noqa: F401
from app.gamification import models as _gamification_models  # noqa: F401
from app.chat import models as _chat_models  # noqa: F401
from app.learning import models as _learning_models  # noqa: F401
from app.assessment import models as _assessment_models  # noqa: F401
from app.certification import models as _certification_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# URL real inyectada en runtime desde la configuración de la app.
config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Genera el SQL de las migraciones sin conectarse a la base (modo offline)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# Ancho de la columna `version_num` de la tabla de control de Alembic. Alembic la
# crea por defecto como VARCHAR(32), pero algunos identificadores de revisión del
# proyecto superan los 32 caracteres (p. ej. `0004_learning_microcapsulas_rutas`),
# lo que rompía `alembic upgrade` desde cero. Se asegura un ancho holgado.
_VERSION_NUM_LENGTH = 255


def _ensure_version_table(connection: Connection) -> None:
    """Crea `alembic_version` con una columna `version_num` suficientemente ancha.

    Si la tabla aún no existe, se crea con `VARCHAR(255)` para admitir
    identificadores de revisión largos; si ya existe, no se altera. El DDL es
    estático (sin entrada externa), por lo que no hay riesgo de inyección.
    """
    connection.execute(
        text(
            f"CREATE TABLE IF NOT EXISTS alembic_version ("
            f"version_num VARCHAR({_VERSION_NUM_LENGTH}) NOT NULL, "
            f"CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
        )
    )
    # Confirma el DDL en su propia transacción: la conexión asyncpg no está en
    # autocommit, por lo que sin este commit la creación se perdería al abrir
    # Alembic su propia transacción de migraciones.
    connection.commit()


def _do_run_migrations(connection: Connection) -> None:
    # Garantiza el ancho correcto de `version_num` antes de cualquier migración,
    # de modo que un `upgrade` desde cero no falle con revisiones > 32 caracteres.
    _ensure_version_table(connection)
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Aplica las migraciones usando un engine asíncrono (asyncpg)."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
