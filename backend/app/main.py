"""Punto de entrada de la API de CIMA (FastAPI).

Cablea la infraestructura transversal (Correlation-ID, logging estructurado,
manejo global de errores) y los routers de dominio disponibles. A medida que se
ejecutan las tareas del plan, se incorporan más routers aquí.
"""
from fastapi import FastAPI

from app.common.config import get_settings
from app.common.correlation import CorrelationIdMiddleware
from app.common.errors import register_error_handlers
from app.common.logging import configure_logging
from app.profile.router import router as profile_router

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title="CIMA API",
    description="Escuela de Sostenibilidad e Inclusión Bolívar",
    version="0.1.0",
)

# Infraestructura transversal.
app.add_middleware(CorrelationIdMiddleware)
register_error_handlers(app)

# Routers de dominio.
app.include_router(profile_router)


@app.get("/api/v1/health", tags=["health"])
async def health() -> dict[str, str]:
    """Verificación de estado del servicio."""
    return {"status": "ok", "env": settings.app_env}
