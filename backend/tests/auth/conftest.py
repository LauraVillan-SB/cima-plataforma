"""Configuración de las pruebas de autenticación.

Las cookies de sesión se prueban como en stage/prod (`COOKIE_SECURE=true`). En local
`backend/.env` suele tener `COOKIE_SECURE=false` para poder entrar por HTTP, y eso
hacía fallar las pruebas que verifican el atributo `Secure`. Las variables de entorno
tienen prioridad sobre `.env` en pydantic-settings.
"""

from __future__ import annotations

import pytest

from app.common.config import get_settings


@pytest.fixture(autouse=True)
def _cookies_seguras(monkeypatch: pytest.MonkeyPatch):
    """Fuerza `COOKIE_SECURE=true` en cada prueba de este paquete."""
    monkeypatch.setenv("COOKIE_SECURE", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
