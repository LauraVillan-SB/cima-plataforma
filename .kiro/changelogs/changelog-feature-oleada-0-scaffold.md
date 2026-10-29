# Changelog — feature/oleada-0-scaffold

## [No publicado]

### Agregado
- Se agregó la capa de acceso a datos del backend (`app/common/database.py`): engine asíncrono de SQLAlchemy con asyncpg, pool de conexiones acotado y dependencia `get_session` para FastAPI.
- Se agregó la configuración de Alembic (`alembic.ini`) para migraciones, con la URL de BD inyectada en runtime desde la configuración (sin hardcodear).
