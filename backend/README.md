# CIMA — Backend (FastAPI)

Backend de la plataforma CIMA (Escuela de Sostenibilidad e Inclusión Bolívar).

## Stack

- Python 3.12+ · FastAPI · SQLAlchemy · Pydantic · Alembic
- PostgreSQL 15+ con PgVector
- pytest + Hypothesis (property-based testing)

Dependencias ancladas a versión exacta y resueltas desde JFrog.

## Estructura

```
app/
  auth/           Autenticación sin fricción (teléfono + Clave de 4 dígitos)
  chat/           Agente conversacional (IA responsable, voz-first)
  learning/       Micro-aprendizaje y adaptativo
  conversion/     Incentivos y microseguros
  certification/  Certificación
  assessment/     Evaluaciones
  metrics/        Métricas por zona y Tablero ODS
  profile/        Perfil y protección de datos
  sync/           Sincronización offline idempotente
  gamification/   Insignias y puntos
  survey/         Encuesta de satisfacción
  common/         Configuración y utilidades transversales
```

## Puesta en marcha (local)

```bash
cp .env.example .env   # completar valores locales (sin secretos reales)
poetry install
poetry run uvicorn app.main:app --reload
poetry run pytest
```

Healthcheck: `GET /api/v1/health`

## Migraciones (Alembic)

```bash
poetry run alembic upgrade head   # aplica las migraciones pendientes
poetry run alembic heads          # debe mostrar UN solo head
poetry run alembic history        # historial de revisiones
```

- Las revisiones están en `alembic/versions/` y forman una cadena (`0001`, `0002`, ...).
  Cada migración nueva debe apuntar (`down_revision`) a la última existente.
- Antes de abrir un PR con una migración, corre `alembic heads`. Si muestra más de un
  head (dos personas crearon una migración a partir de la misma), hay que acordar el
  orden y encadenarlas antes de fusionar.
- Los modelos de cada dominio se registran en `alembic/env.py` para `--autogenerate`.
- La nota de la Tarea 4.2 en `.kiro/specs/cima-plataforma/tasks.md` indica qué tablas
  aún no tienen migración.

## Convenciones

- Rutas versionadas con prefijo `/api/v1/`; OpenAPI como fuente de verdad.
- Validación en servidor (Pydantic); autorización siempre en backend.
- PII enmascarada en respuestas y logs; secretos vía Secret Manager / env.

Especificación completa en `.kiro/specs/cima-plataforma/`.
