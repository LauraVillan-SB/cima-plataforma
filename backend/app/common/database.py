"""Configuración de acceso a la base de datos (SQLAlchemy async).

Define el engine asíncrono, la factoría de sesiones y la clase base declarativa.
La URL proviene de la configuración (variables de entorno / Secret Manager),
nunca hardcodeada.
Requisito: 17.4 (base para persistencia).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.common.config import get_settings

settings = get_settings()

# El pool se gestiona por defecto por SQLAlchemy; la URL nunca va en el código.
engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    """Clase base declarativa para todos los modelos ORM."""


async def get_db() -> AsyncIterator[AsyncSession]:
    """Dependencia de FastAPI que entrega una sesión y la cierra al terminar."""
    async with SessionLocal() as session:
        yield session
