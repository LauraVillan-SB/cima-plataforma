# Colecciones Postman

Debe existir una colección Postman por cada operación del backend.
Se irán agregando a medida que se implementen los servicios de dominio.

## Colecciones disponibles

| Archivo | Servicio | Operaciones |
|---|---|---|
| `conversion.postman_collection.json` | Conversion (Tarea 16.2) | `GET /api/v1/conversion/microseguros/{ruta_id}`, `POST /api/v1/conversion/intenciones/{ruta_id}` + casos de rechazo |
| `gamificacion.postman_collection.json` | Gamification (Tarea 17.2) | `GET /api/v1/gamificacion/reconocimientos` + casos de rechazo (perfil ajeno, formato inválido, sin sesión) |
| `chat.postman_collection.json` | Conversational Agent (Tareas 11.1-11.6) | `POST /api/v1/chat/mensajes`, `POST /api/v1/chat/mensajes/voz`, `GET /api/v1/chat/mensajes/{id}`, `GET /api/v1/chat/historial` + casos de rechazo (mensaje vacío, clave inesperada, mensaje ajeno, id inválido) |

Pendientes: auth, profile, metrics, survey, sync (y los servicios que aún no se implementan).
El otorgamiento de reconocimientos no se expone por HTTP; lo invoca el Learning Service
dentro del backend (ver Tarea 17.1 en `tasks.md`).

## Cómo usarlas (local)

1. En `backend/.env` pon `COOKIE_SECURE=false`: la sesión viaja en una cookie `Secure` y
   Postman no la envía por HTTP si está activa. **Solo en local**; en stage/prod debe ser `true`.
2. Levanta el backend (`poetry run uvicorn app.main:app --reload`) con una base de datos
   que tenga aplicadas las migraciones (`poetry run alembic upgrade head`).
3. Importa el archivo `.json` en Postman (File > Import).
4. En las variables de la colección completa `telefono` y `clave` con un usuario **de
   prueba local**. Nunca guardes credenciales reales ni subas el archivo con valores.
5. Ejecuta primero `0. Ingreso`: guarda la cookie `cima_access` en el cookie jar de
   Postman y las demás solicitudes la envían solas.

## Convenciones

- Una colección por servicio de dominio, con nombre `<servicio>.postman_collection.json`.
- Cada colección empieza con el ingreso, incluye las pruebas de Postman (`pm.test`) y los
  casos de rechazo relevantes (validación, anti-BOLA, sesión).
- Sin secretos ni datos personales reales: usa variables vacías y UUID ficticios.
