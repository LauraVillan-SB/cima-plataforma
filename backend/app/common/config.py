"""Configuración central del backend CIMA cargada desde variables de entorno."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la aplicación. Los secretos provienen de env/Secret Manager."""

    app_env: str = "dev"
    database_url: str = "postgresql+asyncpg://cima_app:CHANGE_ME@localhost:5432/cima"
    jwt_issuer: str = "https://idp.segurosbolivar.com"
    access_token_ttl_seconds: int = 900
    session_inactivity_seconds: int = 1800
    http_allowlist_domains: str = "sostenibilidadbolivar.com"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración cacheada de la aplicación."""
    return Settings()
