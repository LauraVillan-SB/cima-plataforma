"""Configuración central del backend CIMA cargada desde variables de entorno."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la aplicación. Los secretos provienen de env/Secret Manager."""

    app_env: str = "dev"
    database_url: str = "postgresql+asyncpg://cima_app:CHANGE_ME@localhost:5432/cima"
    jwt_issuer: str = "https://idp.segurosbolivar.com"
    access_token_ttl_seconds: int = 900
    # TTL del refresh token (14 días). Con rotación: cada refresco emite uno nuevo.
    refresh_token_ttl_seconds: int = 1209600
    session_inactivity_seconds: int = 1800
    # Secreto de firma de los tokens de sesión. En dev usa un valor por defecto NO
    # apto para producción; en stage/prod proviene de Secret Manager vía entorno.
    session_secret: str = "dev-only-insecure-change-me"
    # `cookie_secure` se desactiva solo en dev (HTTP local); en stage/prod es True.
    cookie_secure: bool = True
    cookie_samesite: str = "lax"
    http_allowlist_domains: str = "sostenibilidadbolivar.com"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración cacheada de la aplicación."""
    return Settings()
