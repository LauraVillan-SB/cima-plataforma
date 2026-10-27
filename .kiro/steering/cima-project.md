---
inclusion: always
---

# CIMA — Contexto del proyecto

CIMA (Conocimiento, Inteligencia, Mercado y Agro) es la **plataforma educativa** de la
Escuela de Sostenibilidad e Inclusión de Seguros Bolívar: una PWA ultraligera que forma a
agricultores y tenderos colombianos en finanzas, gestión de riesgos y adaptación al clima,
con un asistente conversacional voz-first.

Este steering orienta a Kiro al trabajar en CIMA. Las reglas transversales de la compañía
(tech-stack, arquitectura, seguridad, code-style, changelog) siguen aplicando; esto solo
añade el contexto específico del proyecto.

## Alcance (crítico — no inventar)

- CIMA **educa** y **mide el interés**. Nada más.
- **No procesa pagos.** No hay pasarela de pagos.
- **No emite pólizas.** No se integra con ningún core de aseguramiento.
- La conversión a microseguro **solo registra la intención** del usuario como dato para
  análisis.

Si una tarea implica pagos o emisión de pólizas, está fuera de alcance: detente y acláralo.

## Fuentes de verdad (en este orden)

1. Requisitos (EARS): `.kiro/specs/cima-plataforma/requirements.md` — el "qué".
2. Diseño técnico: `.kiro/specs/cima-plataforma/design.md` — el "cómo".
3. Arquitectura explicada: `docs/ARCHITECTURE.md` y `docs/ARCHITECTURE-AWS.md`.
4. Tareas: `.kiro/specs/cima-plataforma/tasks.md`.

Antes de implementar, verifica el requisito asociado y cita su identificador (Req N) en el
código y en el PR.

## Pila del proyecto

- Frontend: Angular (LTS) como PWA, Service Worker, RxJS, `inject()`, `HttpClient`.
- Backend: FastAPI (Python 3.12+), SQLAlchemy, Pydantic, Alembic, pytest.
- Datos: PostgreSQL 15+ con PgVector; Data Operativa vía GraphQL para métricas ODS.
- Async: cola de mensajes + workers para inferencia de IA, STT/TTS y reintentos.

## Reglas de dominio que no se negocian

- **Acceso sin fricción:** teléfono + Clave de 4 dígitos. La Clave se guarda solo como hash
  (bcrypt/argon2), nunca en texto plano (Req 1).
- **PII mínima y enmascarada:** perfil solo con teléfono, tipo de cultivo/comercio y zona.
  Enmascarar PII en respuestas y logs dejando como máximo los últimos 4 caracteres
  (Req 5.9, Req 9.4). Retención máxima 90 días (Req 8.8, Req 9.8).
- **Autorización por propiedad (anti-BOLA):** validar titularidad del recurso en cada
  petición; nunca confiar en IDs del cliente (Req 6.7, Req 9.6).
- **IA responsable:** redactar PII antes de enviar al modelo; si la redacción falla, no
  invocar el modelo (Req 3.10, Req 3.11). Inferencia asíncrona, registro sin PII (Req 16).
- **Voz-first y accesible:** español coloquial colombiano, WCAG 2.1 AA, operación offline.

## MCP propio del proyecto — `cima-project`

El proyecto expone un MCP propio en `mcp/cima_mcp_server.py` (ver `mcp/README.md`) con
herramientas de dominio. Úsalas cuando apliquen durante el desarrollo:

- `validate_user_profile` — valida un Perfil de Usuario (Req 9).
- `validate_clave` — valida la Clave de 4 dígitos (Req 1).
- `mask_pii` — enmascara PII dejando los últimos N caracteres (Req 5.9 / 9.4).
- `list_requirements` — lista los requisitos del spec para trazabilidad.

Complementa (no reemplaza) los MCP institucionales: `security-audit`, `datadog`,
`cloudwatch`, `aws-api`.

## Agent Hooks del proyecto

- `auto-changelog` (PostFileSave): recuerda actualizar `CHANGELOG.md` ante cambios
  significativos, siguiendo el estándar de la compañía.
- `security-review` (PreToolUse sobre escrituras): revisión OWASP Top 10:2025 antes de
  escribir archivos.

## Convenciones al implementar

- Rutas de API versionadas `/api/v1/...` en camelCase o minúsculas; OpenAPI como contrato.
- Validación estricta en servidor con Pydantic; rechazar claves inesperadas.
- Queries parametrizadas siempre; nunca concatenar SQL.
- Dependencias con versión exacta desde JFrog (sin `^`, `~`, `*`, `latest`).
- Actualizar el `CHANGELOG.md` en el mismo cambio, en español y en tiempo pasado.
