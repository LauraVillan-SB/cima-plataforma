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
    # Bloqueo por intentos fallidos: umbral y duración del bloqueo (Req 1.12, 1.13).
    max_failed_attempts: int = 5
    lockout_seconds: int = 900
    # Secreto de firma de los tokens de sesión. En dev usa un valor por defecto NO
    # apto para producción; en stage/prod proviene de Secret Manager vía entorno.
    session_secret: str = "dev-only-insecure-change-me"
    # `cookie_secure` se desactiva solo en dev (HTTP local); en stage/prod es True.
    cookie_secure: bool = True
    cookie_samesite: str = "lax"
    http_allowlist_domains: str = "sostenibilidadbolivar.com"
    # Control de SSRF para consumo externo (Req 10.4, 10.5): timeout bajo y
    # máximo de redirecciones permitidas en llamadas salientes.
    http_timeout_seconds: float = 5.0
    http_max_redirects: int = 2
    # Circuit breaker para dependencias externas (Req 11.5, 11.6): fallos
    # consecutivos antes de abrir el circuito y segundos antes de reintentar.
    circuit_failure_threshold: int = 5
    circuit_reset_seconds: float = 30.0
    # Retención de datos sensibles: a los 90 días la PII se anonimiza (Req 8.8, 9.8).
    data_retention_days: int = 90
    # Rate limiting de intentos de acceso a recursos ajenos (anti-BOLA, Req 9.7):
    # máximo de intentos bloqueados permitidos por ventana, antes de limitar.
    bola_max_attempts: int = 5
    bola_window_seconds: int = 60
    # Kill switch del Agente Conversacional (Req 16.6): si es True, el agente se
    # degrada y responde solo con el mensaje de respaldo seguro, sin invocar el
    # modelo. Se activa vía variable de entorno ante un incidente operativo.
    chat_agent_enabled: bool = True
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración cacheada de la aplicación."""
    return Settings()
