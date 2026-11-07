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
      "duration_sec": 196,
      "difficulty": 0,
      "title": "Las cuentas del café: qué entra y qué sale en cada cosecha",
      "summary": "Un registro sencillo para saber cuánto cuesta producir y cuánto te queda realmente.",
      "paragraphs": ["Primer párrafo de texto plano...", "Segundo párrafo..."],
      "key_points": ["Primer punto clave...", "Segundo punto clave..."],
      "video": null
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
  "path_id": "00000000-0000-4000-8000-0000000000b1",
  "elapsed_seconds": 210
}
```

`elapsed_seconds` es opcional (entero entre 0 y 86400): lo mide el cliente sin pedirle nada al
usuario y solo alimenta la señal de tiempo. Sin él no hay señal de tiempo.

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
  "adapted": true,
  "simplify": true,
  "pace": "slow"
}
```

`simplify` y `pace` (`standard` o `slow`) son lo que el cliente debe aplicar a la microcápsula
siguiente; el cliente no calcula nada. Sin señales los tres vuelven a `false` y `standard`
(ruta estándar, Req 17.5). Ojo: `adapted` antes significaba "tiene progreso"; ahora significa
"el backend aplicó una adaptación".

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

Resiliencia del registro de eventos (Req 4.7, Property 15): si registrar un evento en Metrics
falla por un error de base de datos, se reintenta hasta 3 veces tras el primer intento (nunca
más), revirtiendo la transacción entre intentos. Si persiste, el evento se guarda en
`learning_event_outbox` (idempotente por `client_event_id`, solo identificadores, sin PII) y la
finalización responde con éxito. Cada finalización del mismo usuario llama a `drain_outbox`,
que registra los pendientes de ese usuario y se detiene en el primer fallo. Cualquier error que
no sea de base de datos se propaga como defecto.

Límites: no hay un worker global que drene la cola; `drain_outbox(db)` sin `profile_id` está
listo para uno, pero un usuario que no vuelve no recupera sus eventos hasta entonces. Si ni
siquiera se puede guardar en la cola (base de datos caída), la petición falla y el reintento del
cliente lo vuelve a intentar. El evento `ruta_completada` solo se emite al pasar a completada,
por lo que ese último caso no lo recupera.

Si no hay coincidencias para la actividad se entrega el tema general (`fallback`) con un aviso en
español coloquial.

Perfil sin actividad (Req 4.8, 4.9): `prompt_activity` indica pedirla. Cada consulta con el Perfil
incompleto cuenta una solicitud en `profile_activity_prompts` (incremento atómico, tope de 3).
Agotadas las 3, `prompt_activity` pasa a `false` y se entrega el tema general sin personalizar
ni aviso. Ojo: se cuenta cada consulta, no cada pregunta realmente hecha por el agente; si la
pantalla recarga el listado puede gastar solicitudes.

Adaptación (Req 17): se capturan señales de la propia actividad, sin pedir datos extra.

- Repetición: finalizar una cápsula ya finalizada con otro `client_event_id`. Reenviar la misma
  petición (mismo `client_event_id`) es un reintento de red y no cuenta.
- Tiempo: `elapsed_seconds` mayor a 2 veces la duración de la cápsula (`EXPECTED_TIME_FACTOR`,
  valor de referencia pendiente de validar con negocio).
- Comprensión: intentos de evaluación sin ninguno aprobado. Al aprobar deja de ser señal.

La señal de repetición y de tiempo marca la microcápsula siguiente como simplificada y a ritmo
lento; la siguiente finalización normal la devuelve al ritmo estándar. Hoy cada ruta es una
secuencia fija de cápsulas y no hay variantes simplificadas del contenido: el backend entrega la
indicación (`simplify`, `pace`) y la presentación simplificada queda del lado del front.

## Contenido y video de apoyo

El catálogo de arranque vive en `catalog.py` y se carga con un comando idempotente:

```bash
cd backend && poetry run python -m app.learning.seed
```

Incluye 9 microcápsulas (3 generales de respaldo, 3 de café y 3 de tienda de barrio, cada
actividad con clima, finanzas y gestión de riesgos), 3 rutas y 3 evaluaciones de 3 preguntas.
Los identificadores salen de `uuid5(slug)`, así que repetir la carga actualiza las mismas filas y
no toca el progreso de nadie; nunca borra. Se niega a correr fuera de `dev`, `local`, `test` y
`stage`. Las otras 10 actividades permitidas reciben el tema general hasta que se agregue su
contenido.

Es contenido de referencia, original y en texto plano (sin enlaces ni HTML), **pendiente de
revisión por la Escuela de Sostenibilidad e Inclusión**. La duración de cada cápsula sale de
contar sus palabras a unos 132 por minuto de lectura en voz alta, y una prueba exige que quede
entre 180 y 300 s. El respaldo sin actividad entrega solo las cápsulas etiquetadas `general`.

Video de apoyo (opcional): una cápsula puede llevar un video de YouTube, pero solo se guarda el
identificador de 11 caracteres más el título y el canal para dar el crédito. Nunca una URL. El
backend arma la dirección con `youtube-nocookie.com` y el DTO rechaza cualquier identificador
con otro formato. El texto es lo principal y funciona sin conexión; el video es un complemento.
Para cargar uno:

1. Verifica que existe, que se puede incrustar y que su contenido es adecuado y de una fuente
   confiable. El endpoint público
   `https://www.youtube.com/oembed?url=<URL del video>&format=json` responde 200 con el título y
   el canal; un 401 o 404 indica que no se puede incrustar o no existe.
2. Agrega `video=VideoSpec(video_id="...", title="...", channel="...")` a la cápsula en
   `catalog.py`, copiando título y canal tal como los informa YouTube.
3. Vuelve a ejecutar la carga.

Pendiente de otros equipos: el front debe mostrar el contenido y el video, y la política de
seguridad de contenido (`frame-src`) tiene que permitir `https://www.youtube-nocookie.com`.
Hoy ninguna cápsula trae video: no se cargó ninguno porque no se pudo verificar uno.

## Tecnologías

FastAPI, SQLAlchemy (async), Pydantic, Alembic (migraciones `0004`, `0012`, `0013` y `0014`), PostgreSQL 15+.

## Pruebas

```bash
cd backend && poetry run pytest tests/learning
```

## Autores

Laura Villan (@LauraVillan-SB), área Learning, Assessment y Certification.
