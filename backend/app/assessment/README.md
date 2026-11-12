# Assessment Service

Presenta la evaluación de una ruta, califica las respuestas en el servidor (0 a 100) y
controla los reintentos y el enfriamiento.

- Requisito: 7 (Evaluación), spec `cima-plataforma`.
- Tarea: 14 de `.kiro/specs/cima-plataforma/tasks.md`.

## API Path

`/api/v1/evaluaciones`

## Endpoints

| Método | Ruta | Descripción | Éxito | Errores |
|---|---|---|---|---|
| GET | `/{ruta_id}` | Presenta preguntas y opciones, sin la clave de respuestas | 200 | 404 sin evaluación, 409 ruta sin completar, 403 sin sesión |
| POST | `/{ruta_id}/respuestas` | Valida, califica y registra un intento | 200 | 404, 409 ruta sin completar o ya aprobada, 422 validación, 429 enfriamiento, 403 sin sesión |

Los intentos se anclan al usuario de la sesión; el cliente nunca envía su identidad (anti-BOLA).

## Ejemplos

`GET /api/v1/evaluaciones/{ruta_id}`

```json
{
  "path_id": "00000000-0000-4000-8000-0000000000b1",
  "questions": [
    {"id": 0, "prompt": "Pregunta de ejemplo", "options": ["Opción A", "Opción B", "Opción C"]}
  ]
}
```

`POST /api/v1/evaluaciones/{ruta_id}/respuestas`

```json
{"answers": [{"question_id": 0, "selected_option": 1}]}
```

Respuesta 200:

```json
{
  "path_id": "00000000-0000-4000-8000-0000000000b1",
  "score": 100,
  "passed": true,
  "attempt_number": 1,
  "attempts_remaining": 0,
  "cooldown_until": null
}
```

Al agotar los 3 intentos sin aprobar, `cooldown_until` trae la fecha ISO-8601 en que se
puede volver a intentar.

## Arquitectura

- `router.py`: rutas HTTP y autenticación; sin lógica de negocio.
- `service.py`: compuerta de ruta completa, validación, cálculo y reintentos.
- `errors.py`: errores 409 propios (`RutaNoCompletadaError`, `EvaluacionYaAprobadaError`).
- `dto.py`: validación estricta (`extra="forbid"`); la salida nunca incluye la opción correcta.
- `models.py`: evaluación (preguntas con su clave, solo en servidor) e intentos.

Orden de las comprobaciones al enviar respuestas, para no filtrar nada antes de tiempo:

1. La evaluación existe (404).
2. El usuario completó la ruta, leyendo el progreso de Learning (409, Req 7.1).
3. No la aprobó ya (409): una evaluación aprobada no se vuelve a calificar (Req 7.3).
4. No está en enfriamiento (429, Req 7.5).
5. Las respuestas son válidas: preguntas conocidas, opción en rango, sin faltantes ni
   duplicados (422, Req 7.6, 7.7). Solo entonces se calcula el puntaje.

El puntaje es la proporción de aciertos redondeada; aprueba con el umbral de la ruta
(70 por defecto). Se permiten 3 intentos no aprobados; al tercero se activa un
enfriamiento de 24 horas y, al vencer, el contador se reinicia (Req 7.4, 7.5).

## Tecnologías

FastAPI, SQLAlchemy (async), Pydantic, Alembic (migración `0005`), PostgreSQL 15+.

## Pruebas

```bash
cd backend && poetry run pytest tests/assessment
```

## Autores

Laura Villan (@LauraVillan-SB), área Learning, Assessment y Certification.
