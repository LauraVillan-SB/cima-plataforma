# Learning Service

Selecciona microcápsulas personalizadas según la actividad del Perfil, registra su
finalización de forma idempotente y expone el estado de la ruta con el siguiente paso.

- Requisitos: 4 (Microcápsulas) y 17 (Adaptación), spec `cima-plataforma`.
- Tarea: 13 de `.kiro/specs/cima-plataforma/tasks.md`.

## API Path

`/api/v1/aprendizaje`

## Endpoints

| Método | Ruta | Descripción | Éxito | Errores |
|---|---|---|---|---|
| GET | `/microcapsulas` | Microcápsulas según la actividad del Perfil autenticado | 200 | 403 sin sesión |
| POST | `/microcapsulas/{id}/finalizar` | Registra la finalización (idempotente) | 201 | 404 cápsula no encontrada, 422 validación, 403 sin sesión |
| GET | `/rutas/{id}` | Estado de la ruta y siguiente paso | 200 | 404 ruta no encontrada, 403 sin sesión |

La actividad y el titular se resuelven siempre en el servidor desde la sesión; el
cliente nunca envía su identidad (anti-BOLA).

## Ejemplos

`GET /api/v1/aprendizaje/microcapsulas`

```json
{
  "items": [
    {
      "id": "00000000-0000-4000-8000-000000000001",
      "topic": "finanzas",
      "activity_tags": ["cafe"],
      "duration_sec": 240,
      "difficulty": 1
    }
  ],
  "fallback": false,
  "prompt_activity": false,
  "notice": null
}
```

`POST /api/v1/aprendizaje/microcapsulas/{id}/finalizar`

```json
{
  "client_event_id": "00000000-0000-4000-8000-0000000000a1",
  "path_id": "00000000-0000-4000-8000-0000000000b1"
}
```

Respuesta 201:

```json
{
  "path_id": "00000000-0000-4000-8000-0000000000b1",
  "microcapsule_id": "00000000-0000-4000-8000-000000000001",
  "path_completed": false,
  "completed_count": 1,
  "total_count": 3
}
```

`GET /api/v1/aprendizaje/rutas/{id}`

```json
{
  "path_id": "00000000-0000-4000-8000-0000000000b1",
  "completed": false,
  "completed_count": 1,
  "total_count": 3,
  "next_microcapsule_id": "00000000-0000-4000-8000-000000000002",
  "adapted": true
}
```

## Arquitectura

- `router.py`: rutas HTTP y autenticación; sin lógica de negocio.
- `service.py`: selección, finalización y estado de ruta.
- `models.py`: microcápsulas, rutas y progreso (`PathProgress` único por perfil y ruta).
- `dto.py`: validación estricta (`extra="forbid"`), tema en allowlist y duración de 180 a 300 s.

Eventos hacia Metrics (importación diferida, sin acoplar los dominios):

- `microcapsula_completada`: se intenta en cada finalización. Su clave de idempotencia es un
  `uuid5` determinista por (usuario, cápsula), así que reintentar no duplica el evento.
- `ruta_completada`: al terminar la última cápsula, con el `client_event_id` de la petición.

Reconocimientos (Gamification, Req 19): tras guardar el progreso se llama a `grant_recognition`
con el titular de la sesión. La insignia de cápsula se intenta siempre y la de ruta mientras la
ruta esté completa (no solo al terminar), así un fallo previo se recupera con el reintento. Las
claves son `uuid5(client_event_id, trigger)`. Si Gamification responde
`ReconocimientoPendienteError` la finalización no falla; cualquier otro error se propaga.

Se usan claves distintas porque Metrics deduplica por `client_event_id`; con una clave común se
perdería uno de los dos eventos al cerrar la ruta.

Si no hay coincidencias para la actividad se entrega el tema general (`fallback`) con un aviso en
español coloquial; si el Perfil no tiene actividad, `prompt_activity` indica pedirla.

## Tecnologías

FastAPI, SQLAlchemy (async), Pydantic, Alembic (migración `0004`), PostgreSQL 15+.

## Pruebas

```bash
cd backend && poetry run pytest tests/learning
```

## Autores

Laura Villan (@LauraVillan-SB), área Learning, Assessment y Certification.
