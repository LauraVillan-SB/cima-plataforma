<!--
Plantilla de Pull Request — CIMA.
Un PR por cambio acotado. Título corto (≤ 70 chars). Detalle en la descripción.
Toda fusión a develop/stage/master requiere al menos una aprobación del owner del área.
-->

## Resumen

<!-- Qué cambia y por qué, en 2–3 líneas. -->

## Área / dominio afectado

<!-- Marca la(s) carpeta(s) tocada(s): auth, profile, learning, assessment,
certification, chat, conversion, gamification, metrics, survey, sync, common, frontend. -->

- Dominio(s):
- Tarea(s) de `tasks.md` relacionadas:

## Tipo de cambio

- [ ] `feature` — nueva funcionalidad
- [ ] `fix` — corrección de error
- [ ] `chore` — mantenimiento / dependencias / config
- [ ] `docs` — documentación
- [ ] `refactor` — refactor sin cambio de comportamiento

## Cómo se probó

<!-- Comandos ejecutados y resultado. Ej: poetry run pytest / npm test -->

## Checklist

- [ ] La rama sigue el naming `<tipo>/descripcion-corta` (hackathon, sin código Jira)
- [ ] Commits con formato `tipo: descripción corta` (asunto ≤ 40 chars)
- [ ] Pruebas locales en verde (`poetry run pytest` y/o `npm test`)
- [ ] **Sin secretos** en el código ni en el historial (sin `.env`, tokens, llaves)
- [ ] Dependencias ancladas a versión exacta (sin `^`, `~`, `*`)
- [ ] PII enmascarada en respuestas y logs; validación en servidor
- [ ] `CHANGELOG.md` actualizado en la sección **[No publicado]**
- [ ] Respeta la separación de capas (sin lógica de negocio en el frontend)
- [ ] Solo toqué archivos de mi área, o incluí a los owners afectados como revisores

## Notas para los revisores

<!-- Puntos que requieren atención especial, decisiones de diseño, pendientes. -->
