"""Fixtures comunes de las pruebas del chat.

Las pruebas del worker usan sesiones falsas que solo implementan `get`, `commit` y
`refresh`. Desde que el asistente propone acciones, el worker lee las rutas
pendientes del Usuario con el Learning Service, que necesita una base real. Por
defecto se reemplaza esa lectura por "sin rutas"; las pruebas de acciones la
sobrescriben con sus propias rutas.
"""

from __future__ import annotations

import pytest

from app.chat import service


@pytest.fixture(autouse=True)
def _sin_rutas_pendientes(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _ninguna(_db: object, _profile_id: object) -> list:
        return []

    monkeypatch.setattr(service, "_rutas_pendientes", _ninguna)
