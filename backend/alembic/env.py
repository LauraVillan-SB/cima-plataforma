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
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.common.config import get_settings
from app.common.database import Base

# Importa los modelos para poblar Base.metadata (necesario para autogenerate).
# A medida que se creen modelos en otros dominios, se importan aquí.
from app.profile import models as _profile_models  # noqa: F401
from app.metrics import models as _metric_models  # noqa: F401

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


def _do_run_migrations(connection: Connection) -> None:
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
