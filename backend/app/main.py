"""Punto de entrada de la API de CIMA (FastAPI).

Scaffold inicial: expone únicamente el healthcheck versionado. Los routers de
cada dominio (auth, chat, learning, ...) se incorporan al ejecutar las tareas
del plan de implementación.
"""
from fastapi import FastAPI

from app.common.config import get_settings

settings = get_settings()

app = FastAPI(
    title="CIMA API",
    description="Escuela de Sostenibilidad e Inclusión Bolívar",
    version="0.1.0",
)


@app.get("/api/v1/health", tags=["health"])
async def health() -> dict[str, str]:
    """Verificación de estado del servicio."""
    return {"status": "ok", "env": settings.app_env}
