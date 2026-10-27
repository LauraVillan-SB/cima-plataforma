# Guía de Colaboración — CIMA

Esta guía define cómo trabajamos los cuatro integrantes del equipo sobre este
repositorio. Es de obligatorio cumplimiento: respetarla mantiene el historial
limpio, evita conflictos de merge y hace visible la colaboración.

Sigue el estándar de Git de Seguros Bolívar, adaptado al alcance de un proyecto
de hackathon (AWS): sin código Jira y con un modelo de ramas simplificado.

## Modelo de ramas

Para el hackathon trabajamos con dos ramas principales. **Nunca se desarrolla
directo sobre ellas.**

| Rama | Propósito |
|---|---|
| `main` | Código estable y entregable |
| `develop` | Integración continua del equipo |

Flujo: `feature/...` → `develop` → `main`.

Las ramas de trabajo (`feature/...`, `fix/...`) se crean **desde `develop`** y
se integran de vuelta a `develop` vía PR. Cuando `develop` está estable, se
promueve a `main` vía PR.

## Nomenclatura de ramas

Formato: `<tipo>/descripcion-corta-con-guiones`.

Como es un proyecto de hackathon (sin Jira), **se omite el código de historia**.
Palabras separadas por guiones, en minúscula.

```
feature/auth-ingreso-telefono
fix/perfil-validacion-zona
chore/anclar-dependencias-jfrog
docs/guia-colaboracion
```

Tipos válidos: `feature`, `fix`, `hotfix`, `chore`, `docs`, `refactor`.

## Formato de commits

Estructura: `tipo: descripción corta` en el asunto (≤ 40 caracteres), y un
cuerpo opcional con el detalle (≤ 50 caracteres por línea).

```
feature: ingreso por telefono y clave
Implementa POST /api/v1/auth/ingreso con error
generico que no revela existencia del telefono.
```

## Pull Requests

- Toda fusión a `develop` o `main` requiere un **PR aprobado**.
- Mínimo **una aprobación** del owner del área afectada (ver `CODEOWNERS`).
- Usa la plantilla de `.github/pull_request_template.md` y completa el checklist.
- Título corto (≤ 70 caracteres); el detalle va en la descripción.
- Si el control automático marca "PR WITH ERROR", resuelve el problema y, una
  vez corregido el ciclo de error, no sigas empujando cambios al mismo PR.

## Distribución del trabajo

Repartimos por **servicio de dominio**: cada carpeta de `backend/app/<dominio>`
es un límite aislado, lo que reduce los conflictos de merge. Cada integrante es
owner (revisor) de su área en `CODEOWNERS`.

| Integrante | Área | Carpetas |
|---|---|---|
| @patriciatapia-bot | Identidad y perfil | `auth/`, `profile/` |
| @LauraVillan-SB | Aprendizaje y evaluación | `learning/`, `assessment/`, `certification/` |
| @angelamora-tech | IA conversacional y conversión | `chat/`, `conversion/`, `gamification/` |
| @useransible25 | Datos, sync y frontend | `metrics/`, `survey/`, `sync/`, `common/`, `frontend/` |

Las piezas compartidas (`common/`, `main.py`, `pyproject.toml`, `.kiro/specs/`,
`.github/`) requieren **revisión cruzada** de todo el equipo.

## Cómo ejecutar las tareas

El plan de implementación vive en `.kiro/specs/cima-plataforma/tasks.md`, con un
grafo de dependencias en 14 oleadas al final. Toma tareas de tu área respetando
ese orden. Las sub-tareas marcadas con `*` son pruebas opcionales para un MVP
más rápido; el núcleo funcional nunca es opcional.

## Reglas transversales (no negociables)

- Dependencias ancladas a versión exacta (sin `^`, `~`, `*`), desde JFrog.
- Validación en servidor; autorización siempre en backend (nunca en el cliente).
- PII enmascarada en respuestas y logs; sin secretos en el código ni en el repo.
- Separación de capas: el frontend solo renderiza, sin lógica de negocio.
- Actualiza `CHANGELOG.md` (sección **[No publicado]**) en cada PR relevante.

## Checklist rápido antes de abrir un PR

1. Rama con naming correcto y creada desde `develop`.
2. Commits con el formato acordado.
3. `poetry run pytest` y/o `npm test` en verde.
4. Sin secretos ni `.env` en el diff.
5. `CHANGELOG.md` actualizado.
6. Plantilla de PR completada y owner del área como revisor.
