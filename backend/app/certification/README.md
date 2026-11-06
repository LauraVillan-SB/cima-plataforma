# Certification Service

Emite el Certificado de una ruta cuando el usuario la completó y aprobó la evaluación, y
permite consultarlo solo a su titular.

- Requisito: 6 (Certificación), spec `cima-plataforma`.
- Tarea: 15 de `.kiro/specs/cima-plataforma/tasks.md`.

## API Path

`/api/v1/certificados`

## Endpoints

| Método | Ruta | Descripción | Éxito | Errores |
|---|---|---|---|---|
| POST | `` | Emite el Certificado de la ruta (idempotente) | 201 | 422 ruta sin completar o evaluación no aprobada, 422 cuerpo inválido, 403 sin sesión |
| GET | `/{certificado_id}` | Consulta un Certificado propio | 200 | 404 inexistente, 403 de otro titular o sin sesión |

El titular sale siempre de la sesión: el cuerpo solo lleva `path_id` y cualquier otro campo
se rechaza (anti-BOLA).

## Ejemplos

`POST /api/v1/certificados`

```json
{"path_id": "00000000-0000-4000-8000-0000000000b1"}
```

Respuesta 201:

```json
{
  "id": "00000000-0000-4000-8000-0000000000c1",
  "path_id": "00000000-0000-4000-8000-0000000000b1",
  "verification_code": "CODIGO-DE-EJEMPLO",
  "issued_at": "2026-01-01T12:00:00+00:00"
}
```

Repetir la solicitud devuelve el mismo Certificado, sin crear otro. `GET /{certificado_id}`
responde con la misma forma. La respuesta no incluye el identificador del titular.

## Arquitectura

- `router.py`: rutas HTTP y autenticación; sin lógica de negocio.
- `service.py`: verifica las condiciones, emite y consulta con autorización por titular.
- `dto.py`: validación estricta (`extra="forbid"`) y salida con lista blanca de campos.
- `constants.py`: generación del código de verificación.
- `models.py`: Certificado, único por (perfil, ruta).

Para emitir, el servidor comprueba dos condiciones leyendo los otros dominios:

1. La ruta está completa para el usuario, según Learning (Req 4.10).
2. Existe un intento aprobado de la evaluación, según Assessment (Req 6.1).

Si falta alguna se rechaza sin emitir (Req 6.2). La idempotencia (Req 6.4) la garantiza una
restricción única en base de datos, además de la búsqueda previa.

Al consultar, un Certificado inexistente responde 404 sin revelar datos; uno de otro titular
responde 403 y deja un registro del intento sin PII ni contenido (Req 6.6, 6.7).

## Tecnologías

FastAPI, SQLAlchemy (async), Pydantic, Alembic (migración `0006`), PostgreSQL 15+.

## Pruebas

```bash
cd backend && poetry run pytest tests/certification
```

## Autores

Laura Villan (@LauraVillan-SB), área Learning, Assessment y Certification.
