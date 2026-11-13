"""Configuración común de las pruebas del backend.

Las pruebas nunca llaman a proveedores externos de IA. Aunque `backend/.env`
active un proveedor real (`CHAT_LLM_PROVIDER=gemini`) para uso local, durante
las pruebas se fuerza el respaldo seguro: las variables de entorno tienen
prioridad sobre `.env` en pydantic-settings. Las pruebas del adaptador usan un
transporte simulado y su propia configuración.
"""

from __future__ import annotations

import os

import pytest

from app.common.config import get_settings


@pytest.fixture(autouse=True, scope="session")
def _sin_proveedor_de_ia_real():
    """Fuerza `CHAT_LLM_PROVIDER=respaldo` durante toda la sesión de pruebas."""
    previo = os.environ.get("CHAT_LLM_PROVIDER")
    os.environ["CHAT_LLM_PROVIDER"] = "respaldo"
    get_settings.cache_clear()
    yield
    if previo is None:
        os.environ.pop("CHAT_LLM_PROVIDER", None)
    else:
        os.environ["CHAT_LLM_PROVIDER"] = previo
    get_settings.cache_clear()
