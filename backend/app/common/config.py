"""Configuración central del backend CIMA cargada desde variables de entorno."""
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la aplicación. Los secretos provienen de env/Secret Manager."""

    app_env: str = "dev"
    database_url: str = "postgresql+asyncpg://cima_app:CHANGE_ME@localhost:5432/cima"
    jwt_issuer: str = "https://idp.segurosbolivar.com"
    access_token_ttl_seconds: int = 900
    # Tope absoluto de una sesión desde el ingreso (14 días): aunque haya
    # actividad, pasado este plazo hay que volver a autenticarse.
    refresh_token_ttl_seconds: int = 1209600
    # Inactividad máxima (30 min, Req 1.14): el refresh vence a los 30 min de la
    # última petición autenticada y cada petición lo renueva. Debe ser mayor que
    # `access_token_ttl_seconds` para que el refresco cubra el hueco entre ambos.
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
    # Proveedor del modelo del Agente Conversacional (Tarea 11.4). Por defecto el
    # respaldo seguro, sin llamadas externas; "gemini" usa la API de Gemini.
    chat_llm_provider: Literal["respaldo", "gemini"] = "respaldo"
    # API key de Gemini: solo desde backend/.env (local) o Secret Manager
    # (stage/prod). `SecretStr` evita que aparezca al imprimir la configuración.
    gemini_api_key: SecretStr | None = None
    # Nombre del modelo; patrón estricto porque va en la ruta de la URL.
    gemini_model: str = Field(default="gemini-3.8-flash", pattern=r"^[a-z0-9][a-z0-9.\-]{0,62}$")
    # Un LLM tarda más que una API corriente; el worker además corta a los 60 s.
    gemini_timeout_seconds: float = Field(default=30.0, gt=0, le=60)
    gemini_max_output_tokens: int = Field(default=1024, ge=64, le=8192)
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración cacheada de la aplicación."""
    return Settings()
