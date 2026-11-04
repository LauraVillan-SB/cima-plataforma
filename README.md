# CIMA — Conocimiento, Inteligencia, Mercado y Agro

Plataforma de la **Escuela de Sostenibilidad e Inclusión Bolívar**: una PWA ultraligera
con un agente conversacional de IA generativa que escala la educación financiera y
climática y la conversión a microseguros para agricultores y tenderos colombianos.

## Monorepo

| Carpeta | Descripción |
|---|---|
| `backend/` | API FastAPI (Python 3.12+) con PostgreSQL 15+ / PgVector |
| `frontend/` | PWA Angular (voz-first, offline, accesible) |
| `postmanCollections/` | Colecciones Postman por operación |
| `.kiro/specs/cima-plataforma/` | Especificación: requisitos, diseño y tareas |
| `docs/` | Documentación complementaria |

## Funcionalidades (según la especificación)

1. Autenticación sin fricción (teléfono + Clave de 4 dígitos)
2. PWA ultraligera de bajo consumo de datos
3. Agente conversacional por texto y voz
4. Micro-aprendizaje personalizado y adaptativo
5. Conversión a negocio e incentivos / microseguros
6. Certificación de procesos formativos
7. Evaluaciones del aprendizaje
8. Métricas por zona geográfica y Tablero de Impacto (ODS)
9. Gestión del Perfil y protección de datos (Habeas Data)
10. Integración opcional con WordPress
11. Observabilidad y operación
12. Escalabilidad y costo marginal bajo
13. Accesibilidad e inclusión (WCAG 2.1 AA)
14. Experiencia voz-first (STT/TTS)
15. Tablero de impacto social (ODS)
16. IA responsable y gobernada
17. Aprendizaje adaptativo
18. Resiliencia offline
19. Gamificación e insignias
20. Encuesta de satisfacción

## Estado

En desarrollo. La implementación sigue `.kiro/specs/cima-plataforma/tasks.md`, donde cada
tarea indica su estado (`[x]` completa, `[~]` parcial con una nota de lo pendiente) y la
cadena de dependencias. Los cambios se registran en `CHANGELOG.md`.

Con código en `develop`:

- **Backend:** autenticación, perfil, métricas, encuestas, sincronización offline,
  conversión (oferta de microseguros e intención) y gamificación (otorgamiento y consulta
  de insignias y puntos). El chat tiene la validación de entrada y la redacción de PII;
  falta el pipeline de IA.
- **Frontend:** PWA con shell offline, autenticación sin fricción y control de voz.

Pendiente: micro-aprendizaje, evaluaciones y certificación (carpetas `learning/`,
`assessment/` y `certification/` aún vacías), el pipeline de IA (STT, LLM, TTS) y la
integración final.

Para colaborar, ver `CONTRIBUTING.md`. Para las colecciones de prueba de los endpoints,
ver `postmanCollections/`.

## Autores

Equipo CIMA — Seguros Bolívar.
