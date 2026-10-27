"""Capa de acceso a datos de CIMA.

Configura el engine asíncrono de SQLAlchemy y la fábrica de sesiones con pool
de conexiones. La URL de conexión proviene de la configuración (variables de
entorno / Secret Manager), nunca hardcodeada. Se usa asyncpg como driver.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.common.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos ORM de los dominios."""


def _create_engine() -> AsyncEngine:
    """Crea el engine asíncrono con pool de conexiones acotado.

    pool_pre_ping evita usar conexiones muertas tras cortes de red; los límites
    de pool protegen a PostgreSQL ante picos de carga (resiliencia, Req 12).
    """
    return create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800,
    )


engine: AsyncEngine = _create_engine()

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia de FastAPI que entrega una sesión por request.

    Garantiza cierre y rollback ante error, sin filtrar conexiones del pool.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
