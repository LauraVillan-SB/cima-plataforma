# Gamification Service

Otorga Insignias y puntos cuando alguien completa una microcápsula o una ruta, y expone el
resumen de avance (puntos, nivel, racha, Insignias) y un ranking seudónimo.

- Requisito: 19 (Gamificación e insignias), spec `cima-plataforma`.
- Tarea: 17 de `.kiro/specs/cima-plataforma/tasks.md`.
- **Nivel, racha y ranking son una extensión de experiencia que no está en `requirements.md`**
  (el Req 19 solo pide puntos e Insignias). Se derivan de datos que ya tiene el backend y sus
  valores son de referencia, pendientes de validar con negocio.

## API Path

`/api/v1/gamificacion`

## Endpoints

| Método | Ruta | Descripción | Éxito | Errores |
|---|---|---|---|---|
| GET | `/reconocimientos` | Insignias y total de puntos del titular | 200 | 403 de otro perfil o sin sesión |
| GET | `/resumen` | Puntos, nivel, racha e Insignias (con las pendientes) | 200 | 403 sin sesión |
| GET | `/ranking?tamano=N` | Top N por puntos y la posición del titular | 200 | 403 sin sesión, 422 si `tamano` no está entre 1 y 50 |

El otorgamiento **no** se expone por HTTP: lo invoca el Learning Service dentro del backend,
porque un endpoint abierto permitiría darse reconocimientos sin completar nada (Req 19.3). Todo
se ancla al usuario de la sesión; ningún endpoint recibe un identificador de perfil propio.

## Ejemplos

`GET /api/v1/gamificacion/resumen`

```json
{
  "total_points": 60,
  "streak_days": 3,
  "level": {"number": 2, "name": "Aprendiz", "min_points": 50},
  "next_level": {"number": 3, "name": "Conocedor", "points_needed": 90},
  "level_progress_pct": 10,
  "badges": [
    {"badge_code": "primer_paso", "badge_name": "Primer paso", "points": 10, "earned": true},
    {"badge_code": "ruta_completada", "badge_name": "Ruta completada", "points": 50, "earned": false}
  ]
}
```

`GET /api/v1/gamificacion/ranking?tamano=3`

```json
{
  "entries": [
    {"rank": 1, "alias": "Participante 2699", "total_points": 300, "level_name": "Explorador financiero", "streak_days": 4, "is_me": false}
  ],
  "me": {"rank": 8, "alias": "Participante D787", "total_points": 60, "level_name": "Aprendiz", "streak_days": 3, "is_me": true},
  "participants": 12
}
```

## Arquitectura

- `service.grant_recognition`: otorga la Insignia y sus puntos de forma idempotente (Req 19.5, 19.6).
- `service.record_activity`: cuenta el día de actividad para la racha. Es un único
  `INSERT ... ON CONFLICT DO UPDATE` con `CASE`, así que es atómico e idempotente por día: ocho
  llamadas simultáneas el mismo día dejan una sola racha. Lo llama el Learning Service en cada
  finalización y un fallo allí no rompe la finalización.
- `service.level_for`: el nivel se calcula de los puntos (`constants.LEVELS`), no se guarda.
- Racha: con actividad hoy o ayer sigue; con más de un día sin actividad se muestra 0.
- Ranking: solo participan quienes tienen puntos; los empates comparten posición. Cada fila lleva
  un alias derivado de un hash del identificador (`Participante 2699`), nunca teléfono, nombre,
  zona ni id real. El titular aparece resaltado y con su posición aunque quede fuera del top.

## Pendiente

- Mostrar el ranking de otras personas es una decisión de privacidad que debe validar negocio
  antes de producción (hoy solo se ven alias y puntos).
- Los puntos solo se dan por Insignia (una vez): no hay puntos por cada microcápsula.
- No existe tienda de canje ni beneficios: CIMA no procesa pagos ni entrega beneficios, y el
  Req 19.4 (elegibilidad de beneficio sobre un microseguro) sigue sin regla de negocio.

## Tecnologías

FastAPI, SQLAlchemy (async), Pydantic, Alembic (migraciones `0003` y `0015`), PostgreSQL 15+.

## Pruebas

```bash
cd backend && poetry run pytest tests/gamification
```

## Autores

Servicio base: `@angelamora-tech`. Resumen, nivel, racha y ranking: Laura Villan
(@LauraVillan-SB), con `@angelamora-tech` como revisora (es su área).
