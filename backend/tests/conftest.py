"""Configuración común de las pruebas del backend.

Las pruebas nunca llaman a proveedores externos de IA. Aunque `backend/.env`
active un proveedor real (`CHAT_LLM_PROVIDER=gemini` o `CHAT_STT_PROVIDER=gemini`)
para uso local, durante las pruebas se fuerza el respaldo seguro: las variables
de entorno tienen prioridad sobre `.env` en pydantic-settings. Las pruebas de los
adaptadores usan un transporte simulado y su propia configuración.
"""

from __future__ import annotations

import os

import pytest

from app.common.config import get_settings

_SIN_PROVEEDOR_REAL = {"CHAT_LLM_PROVIDER": "respaldo", "CHAT_STT_PROVIDER": "respaldo"}


@pytest.fixture(autouse=True, scope="session")
def _sin_proveedor_de_ia_real():
    """Fuerza los respaldos de modelo y de voz durante toda la sesión de pruebas."""
    previos = {nombre: os.environ.get(nombre) for nombre in _SIN_PROVEEDOR_REAL}
    os.environ.update(_SIN_PROVEEDOR_REAL)
    get_settings.cache_clear()
    yield
    for nombre, previo in previos.items():
        if previo is None:
            os.environ.pop(nombre, None)
        else:
            os.environ[nombre] = previo
    get_settings.cache_clear()
