# Implementation Plan: CIMA (Conocimiento, Inteligencia, Mercado y Agro)

## Overview

Este plan convierte el diseño de CIMA en una secuencia de tareas de codificación incrementales. Cada tarea construye sobre las anteriores y termina integrándose con el sistema, sin dejar código huérfano. El backend se implementa en **FastAPI (Python 3.12+)** con SQLAlchemy, Pydantic, Alembic y pytest; el frontend en **Angular (PWA)** con Service Worker. La persistencia usa **PostgreSQL 15+ con PgVector** y métricas consolidadas vía **GraphQL (Data Operativa)**. Las pruebas basadas en propiedades usan **Hypothesis** (backend) y **fast-check** (frontend), mínimo 100 iteraciones por propiedad, etiquetadas con **Feature: cima-plataforma, Property {n}**.

Convenciones:
- Todas las dependencias se anclan a versión exacta (sin `^`, `~`, `*`) desde JFrog.
- Rutas versionadas con prefijo `/api/v1/`; OpenAPI generado por FastAPI es la fuente de verdad.
- Validación estricta en servidor (Pydantic); autorización siempre en backend; PII enmascarada en respuestas y logs.
- Las sub-tareas marcadas con `*` son opcionales (pruebas) y pueden omitirse para un MVP más rápido.

## Tasks

- [x] 1. Configuración del proyecto backend (FastAPI) y base de datos
  - Crear estructura de carpetas por dominio (`auth/`, `chat/`, `learning/`, `conversion/`, `certification/`, `assessment/`, `metrics/`, `profile/`, `sync/`, `common/`)
  - Configurar `pyproject.toml` con Poetry y dependencias ancladas a versión exacta desde JFrog (fastapi, sqlalchemy, pydantic, alembic, psycopg2/asyncpg, passlib, httpx, pytest, hypothesis, pgvector)
  - Configurar conexión a PostgreSQL con HikariCP/pool, variables de entorno vía Secret Manager, y extensión PgVector
  - Inicializar Alembic para migraciones y pytest para pruebas
  - Añadir `.gitignore` (`.idea`, `node_modules`, `.vscode`, `dist`, `__pycache__`, `.pytest_cache`)
  - _Requirements: 12.1, 17.4_

- [~] 2. Configuración del proyecto frontend (Angular PWA)
  - Crear proyecto Angular con Angular CLI y Service Worker (`@angular/service-worker`), dependencias ancladas desde JFrog
  - Configurar performance budgets en el build: bundle inicial ≤ 500 KB y visita posterior ≤ 50 KB
  - Configurar estructura por dominio (feature modules) y `HttpClient` con interceptor base
  - Añadir `fast-check` + Jest para pruebas de lógica pura del frontend
  - _Requirements: 2.1, 2.3, 2.4_
  - Nota: scaffold, Service Worker, interceptor de Correlation-ID, Jest y fast-check listos; budget inicial ≤ 500 KB configurado en `angular.json`. Falta definir y medir el límite de visita posterior ≤ 50 KB.

- [x] 3. Infraestructura transversal: Correlation-ID, logging estructurado y manejo de errores
  - [x] 3.1 Implementar middleware de Correlation-ID en el backend
    - Generar o propagar `Correlation-ID` entrante; inyectarlo en el contexto de request y en toda invocación saliente
    - _Requirements: 11.1_
    - _Properties: 35_
  - [x] 3.2 Implementar logging estructurado con redacción de PII
    - Logger JSON hacia servicio centralizado (nunca archivos locales); redacción/enmascaramiento de PII, tokens y secretos
    - _Requirements: 11.2, 9.4_
    - _Properties: 18_
  - [x] 3.3 Implementar manejador global de errores y utilidades de enmascaramiento
    - Respuesta genérica en español coloquial con `correlation_id`, sin stack traces ni PII; función reutilizable de enmascaramiento (máx. últimos 4 chars)
    - _Requirements: 9.4, 11.2, 11.6_
    - _Properties: 18_
  - [x]* 3.4 Escribir test de propiedad para enmascaramiento de PII
    - **Property 18: Enmascaramiento de PII en respuestas y logs**
    - **Validates: Requirements 5.9, 9.4**
  - [ ]* 3.5 Escribir test de propiedad para propagación del Correlation-ID
    - **Property 35: Propagación del Correlation-ID**
    - **Validates: Requirements 11.1**

- [ ] 4. Modelos de datos y migraciones
  - [x] 4.1 Definir modelos SQLAlchemy y esquemas Pydantic base
    - Crear entidades `profiles`, `microcapsules` (con columna `embedding` VECTOR/PgVector), `learning_paths`, `path_progress`, `assessments`, `assessment_attempts`, `certificates`, `incentives`, `conversion_intents`, `metric_events`, `metric_aggregates`, `ai_interactions`, `badges`, `user_badges`, `user_points`, `surveys`, `survey_responses`
    - Tipado estricto, cifrado at-rest de PII (`phone_e164`), restricción UNIQUE(`profile_id`,`path_id`) en certificados, `client_event_id` UUID v4 para idempotencia
    - Gamificación: `badges` (catálogo con `points_value`), `user_badges` con restricción UNIQUE(`profile_id`,`badge_id`) y `client_event_id` UUID v4 para otorgamiento idempotente, y `user_points` (total de puntos por perfil)
    - Encuesta de satisfacción: `surveys` (definición de preguntas con escala 1–5) y `survey_responses` con restricción UNIQUE(`profile_id`,`path_id`) y `client_event_id` UUID v4 para idempotencia de registro, y `rating` en escala 1–5
    - _Requirements: 1.5, 4.1, 4.2, 6.4, 8.1, 8.2, 9.1, 17.4, 19.2, 19.5, 20.3, 20.6_
  - [~] 4.2 Crear migraciones Alembic iniciales
    - Migración de creación de tablas, extensión PgVector, índices y roles de BD separados (lectura/escritura/admin)
    - Nota: infraestructura Alembic y migración inicial (`profiles`, `metric_events` + PgVector) creadas y validadas con `alembic history`. Los roles de BD separados quedan como provisión de infraestructura (no en migración versionada). Se extenderá al crear el resto de modelos (4.1 completa).
    - _Requirements: 8.1, 17.4_
  - [ ]* 4.3 Escribir pruebas unitarias de los esquemas de datos
    - Validar restricciones, tipos y defaults (p. ej. `pass_threshold` default 70)
    - _Requirements: 4.1, 4.2, 7.3_

- [ ] 5. Checkpoint — Verificar que la base compila y las migraciones aplican
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Profile Service — Perfil y protección de datos (Req 9)
  - [x] 6.1 Implementar validación y normalización del perfil (allowlist, trim)
    - Esquema Pydantic con allowlist de campos (teléfono, tipo de cultivo/comercio, zona); rechazo de claves no permitidas; validación teléfono 7–15 dígitos, tipo en lista permitida, zona ≤ 100 chars
    - _Requirements: 9.1, 9.2, 9.3_
    - _Properties: 30, 31_
  - [x] 6.2 Implementar endpoints de perfil con DTO allowlist y enmascaramiento
    - `POST /api/v1/perfiles`, `GET/PUT /api/v1/perfiles/me`; respuestas con DTO autorizado y PII enmascarada
    - _Requirements: 9.1, 9.4, 9.5_
    - _Properties: 18, 32_
  - [~] 6.3 Implementar autorización por propiedad (anti-BOLA) y rate limiting de abuso
    - Verificación de titularidad en cada request; registro sin PII de intentos ajenos; rate limiting ante patrón repetido
    - _Requirements: 9.6, 9.7_
    - _Properties: 22, 33_
    - Nota: verificación de titularidad (anti-BOLA) implementada en el Profile Service. Falta el rate limiting ante patrón repetido (coordinar con Tarea 10.3).
  - [x] 6.4 Implementar proceso de retención de datos sensibles a 90 días
    - Job que elimina/anonimiza PII con antigüedad ≥ 90 días conservando agregados no identificables
    - _Requirements: 9.8_
    - _Properties: 29_
  - [x]* 6.5 Escribir test de propiedad para allowlist de campos del perfil
    - **Property 30: Allowlist de campos del Perfil**
    - **Validates: Requirements 9.1**
  - [x]* 6.6 Escribir test de propiedad para normalización y validación del perfil
    - **Property 31: Normalización y validación de campos del Perfil**
    - **Validates: Requirements 9.2, 9.3**
  - [ ]* 6.7 Escribir test de propiedad para DTO con allowlist en respuestas
    - **Property 32: DTO con allowlist en respuestas de Perfil**
    - **Validates: Requirements 9.5**
  - [x]* 6.8 Escribir test de propiedad para autorización por propiedad (anti-BOLA)
    - **Property 22: Autorización por propiedad del recurso (anti-BOLA)**
    - **Validates: Requirements 6.5, 6.6, 6.7, 9.6**
  - [x]* 6.9 Escribir test de propiedad para retención a 90 días
    - **Property 29: Retención de datos sensibles a 90 días**
    - **Validates: Requirements 8.8, 9.8**

- [ ] 7. Auth Service — Autenticación sin fricción (Req 1, Req 10)
  - [x] 7.1 Implementar validación y hashing de la Clave de 4 dígitos
    - Validación exacta de 4 dígitos; hashing con sal (bcrypt/argon2 vía passlib); nunca texto plano; doble confirmación en registro
    - _Requirements: 1.3, 1.4, 1.5_
    - _Properties: 1, 2_
  - [x] 7.2 Implementar registro e ingreso con mensaje de error indistinguible
    - `POST /api/v1/auth/registro`, `POST /api/v1/auth/ingreso`; validación E.164; error genérico que no revela existencia del teléfono; mensajes en español coloquial
    - _Requirements: 1.1, 1.2, 1.6, 1.7, 1.8, 1.9_
    - _Properties: 3_
  - [x] 7.3 Implementar emisión y rotación de tokens en cookies seguras
    - Access ≤ 15 min + refresh con rotación; cookies Secure/HttpOnly/SameSite; sin tokens en localStorage; `POST /api/v1/auth/refresco`, `POST /api/v1/auth/salir`
    - _Requirements: 1.10, 1.13_
    - _Properties: 6_
  - [~] 7.4 Implementar bloqueo por intentos, reactivación e inactividad
    - 5 fallos consecutivos → bloqueo 15 min por teléfono; reactivación con contador en cero; invalidación por 30 min de inactividad; `PUT /api/v1/auth/clave` exige Clave actual
    - _Requirements: 1.11, 1.12, 1.13, 1.14_
    - _Properties: 4, 5_
    - Nota: bloqueo por intentos, reactivación y `PUT /api/v1/auth/clave` implementados. Falta la invalidación de sesión por 30 min de inactividad.
  - [~] 7.5 Implementar restauración de sesión y SSO con WordPress
    - `GET /api/v1/auth/sesion` restaura sesión vigente; SSO valida sesión WordPress contra IdP; redirige conservando destino si expiró o >30 min inactividad
    - _Requirements: 2.6, 2.7, 10.1, 10.2_
    - Nota: `GET /api/v1/auth/sesion` implementado. Falta el SSO con WordPress contra el IdP (depende del cliente HTTP seguro, Tarea 9.1).
  - [x]* 7.6 Escribir test de propiedad para validación de la Clave
    - **Property 1: Validación de la Clave de 4 dígitos**
    - **Validates: Requirements 1.4**
  - [x]* 7.7 Escribir test de propiedad para round-trip de hashing
    - **Property 2: Round-trip de hashing de la Clave**
    - **Validates: Requirements 1.5**
  - [x]* 7.8 Escribir test de propiedad para error de ingreso indistinguible
    - **Property 3: Error de ingreso indistinguible**
    - **Validates: Requirements 1.7**
  - [ ]* 7.9 Escribir test de propiedad para bloqueo por intentos fallidos
    - **Property 4: Bloqueo por intentos fallidos consecutivos**
    - **Validates: Requirements 1.11**
  - [ ]* 7.10 Escribir test de propiedad para reactivación tras expirar el bloqueo
    - **Property 5: Reactivación tras expirar el bloqueo**
    - **Validates: Requirements 1.12**
  - [x]* 7.11 Escribir test de propiedad para propiedades del token de sesión
    - **Property 6: Propiedades del token de sesión**
    - **Validates: Requirements 1.10**

- [ ] 8. Checkpoint — Verificar autenticación y perfil end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Control de SSRF para consumo externo (Req 10)
  - [ ] 9.1 Implementar cliente HTTP seguro con allowlist de dominios
    - Allowlist de dominios, HTTPS obligatorio, bloqueo de IPs privadas/link-local, timeout ≤ 5 s, máx. 2 redirecciones; llamadas autenticadas con token firmado; registro de intentos bloqueados con Correlation-ID
    - _Requirements: 10.4, 10.5_
    - _Properties: 34_
  - [ ]* 9.2 Escribir test de propiedad para control de SSRF
    - **Property 34: Control de SSRF en consumo externo**
    - **Validates: Requirements 10.4, 10.5**

- [ ] 10. Observabilidad, resiliencia y escalabilidad (Req 11, Req 12)
  - [ ] 10.1 Implementar circuit breaker, timeout y fallback para dependencias externas
    - Envolver invocaciones a LLM, STT/TTS, pagos y core de pólizas con circuit breaker + timeout bajo + fallback documentado; registrar activación con Correlation-ID sin PII
    - _Requirements: 11.5, 11.6_
  - [ ] 10.2 Exponer señales doradas con SLO y alertas
    - Métricas de latencia, tráfico, errores y saturación por servicio; definición de SLO y disparo de alertas por umbral
    - _Requirements: 11.3, 11.4_
  - [ ] 10.3 Implementar rate limiting en componentes core y sesión en almacén compartido
    - Rate limiting con respuesta de reintento y registro sin PII; sesión en almacén compartido para escalado horizontal sin pérdida; acuse observable (202) para tareas largas
    - _Requirements: 12.2, 12.3, 12.4, 12.5_
    - _Properties: 33_
  - [ ]* 10.4 Escribir test de propiedad para rate limiting
    - **Property 33: Rate limiting en componentes core**
    - **Validates: Requirements 9.7, 12.2, 12.5**
  - [ ]* 10.5 Escribir pruebas de integración de circuit breaker y escalado sin pérdida de sesión
    - Mocks de dependencias que fallan o exceden timeout; verificar fallback; almacén compartido entre instancias
    - _Requirements: 11.5, 11.6, 12.3_

- [ ] 11. Conversational Agent Service — Pipeline de IA responsable y voz-first (Req 3, Req 14, Req 16)
  - [x] 11.1 Implementar validación de entrada de texto y de nota de voz
    - Rechazar texto vacío (tras trim) o > 2000 chars sin invocar el modelo, conservando contenido; rechazar audio fuera de {m4a/aac, ogg, mp3} o duración fuera de [1, 120] s sin invocar STT ni modelo
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
    - _Properties: 7, 8_
    - Nota: validación pura en `app/chat/validation.py` (formato real por firma binaria, tamaño máx. 5 MiB). La duración debe medirse en el servidor; el endpoint de la Tarea 11.3 debe invocar estas funciones antes de encolar STT o inferencia.
  - [ ] 11.2 Implementar redacción de PII previa al modelo
    - Detección y redacción de PII antes de enviar al LLM; si la redacción falla, no enviar y solicitar reformular
    - _Requirements: 3.10, 3.11, 14.6_
    - _Properties: 9_
  - [ ] 11.3 Implementar inferencia asíncrona con cola/worker y endpoints de chat
    - `POST /api/v1/chat/mensajes` encola inferencia y responde 202; `GET /api/v1/chat/mensajes/{id}` y `GET /api/v1/chat/historial`; indicador de procesamiento hasta 60 s y error de servicio no disponible conservando historial
    - _Requirements: 3.1, 3.5, 3.6, 3.7, 3.8, 12.4_
  - [ ] 11.4 Implementar STT/TTS y ramificación por confianza
    - Pipeline STT → redacción → LLM (mensajes system/developer/user separados) → TTS; confianza STT < umbral solicita confirmación/repetición en lenguaje simple; audio conservado solo durante transcripción
    - _Requirements: 3.3, 14.2, 14.3, 14.5, 14.6_
    - _Properties: 9, 38_
  - [ ] 11.5 Implementar guardrails, validación de salida, kill switch y transparencia
    - Guardrails de entrada; validación de salida vs reglas de negocio para ofertas/incentivos; derivación a canal humano/respuesta segura; kill switch; indicación reconocible de IA
    - _Requirements: 16.1, 16.2, 16.3, 16.5, 16.6_
    - _Properties: 39_
  - [ ] 11.6 Implementar registro auditable de IA sin PII
    - Registrar entrada redactada, salida, versión del modelo y decisión del guardrail con Correlation-ID, sin PII
    - _Requirements: 3.9, 16.4_
    - _Properties: 40_
  - [ ]* 11.7 Escribir test de propiedad para validación de longitud de texto
    - **Property 7: Validación de longitud del mensaje de texto**
    - **Validates: Requirements 3.2**
  - [ ]* 11.8 Escribir test de propiedad para validación de la nota de voz
    - **Property 8: Validación de la nota de voz**
    - **Validates: Requirements 3.4**
  - [ ]* 11.9 Escribir test de propiedad para no fuga de PII hacia el modelo
    - **Property 9: No fuga de PII hacia el modelo**
    - **Validates: Requirements 3.10, 3.11, 14.6**
  - [ ]* 11.10 Escribir test de propiedad para ramificación por confianza de STT
    - **Property 38: Ramificación por confianza de STT**
    - **Validates: Requirements 14.5**
  - [ ]* 11.11 Escribir test de propiedad para guardrails y validación de salida
    - **Property 39: Guardrails de entrada y validación de salida de IA**
    - **Validates: Requirements 16.1, 16.2**
  - [ ]* 11.12 Escribir test de propiedad para registro auditable sin PII
    - **Property 40: Registro auditable de IA sin PII**
    - **Validates: Requirements 3.9, 16.4**

- [ ] 12. Checkpoint — Verificar pipeline de IA voz-first con dependencias mockeadas
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 13. Learning Service — Micro-aprendizaje y adaptativo (Req 4, Req 17)
  - [ ] 13.1 Implementar selección personalizada de microcápsulas
    - `GET /api/v1/aprendizaje/microcapsulas`; máx. 10 por tipo de perfil, orden por relevancia desc. y fecha desc.; duración 180–300 s; clasificación en exactamente un tema
    - _Requirements: 4.1, 4.2, 4.3_
    - _Properties: 10, 11, 12_
  - [ ] 13.2 Implementar fallback a tema general y solicitud de perfil incompleto
    - Sin coincidencias → tema "adaptación al clima" + notificación; perfil incompleto → el agente solicita cultivo/comercio hasta 3 veces y luego tema general sin personalización
    - _Requirements: 4.4, 4.5, 4.8, 4.9_
    - _Properties: 13_
  - [ ] 13.3 Implementar finalización de microcápsula y completitud de ruta
    - `POST /api/v1/aprendizaje/microcapsulas/{id}/finalizar` idempotente con reintentos ≤ 3; marcar ruta completada cuando todas las microcápsulas tienen finalización
    - Al registrar la finalización de una microcápsula o la completitud de una ruta, disparar el otorgamiento de insignias/puntos del Gamification Service (ver Tarea 17)
    - Análogamente, la completitud de una ruta habilita la presentación de la Encuesta_de_Satisfaccion del Survey Service (ver nueva Tarea 19)
    - _Requirements: 4.6, 4.7, 4.10_
    - _Properties: 14, 15_
  - [ ] 13.4 Implementar lógica de adaptación en backend (ritmo/simplificación)
    - `GET /api/v1/aprendizaje/rutas/{id}`; adaptar siguiente microcápsula por repetición/exceso de tiempo/fallo de comprensión usando solo señales ya capturadas; evolucionable a PgVector sin cambiar contrato; default a ruta estándar sin señales
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_
  - [ ]* 13.5 Escribir test de propiedad para duración de microcápsula
    - **Property 10: Invariante de duración de microcápsula**
    - **Validates: Requirements 4.1**
  - [ ]* 13.6 Escribir test de propiedad para clasificación temática única
    - **Property 11: Clasificación temática única**
    - **Validates: Requirements 4.2**
  - [ ]* 13.7 Escribir test de propiedad para selección acotada y ordenada
    - **Property 12: Selección personalizada acotada y ordenada**
    - **Validates: Requirements 4.3**
  - [ ]* 13.8 Escribir test de propiedad para fallback a tema general
    - **Property 13: Fallback a tema general sin coincidencias**
    - **Validates: Requirements 4.4, 4.5, 4.9**
  - [ ]* 13.9 Escribir test de propiedad para completitud de ruta
    - **Property 14: Completitud de ruta como bicondicional**
    - **Validates: Requirements 4.10**
  - [ ]* 13.10 Escribir test de propiedad para resiliencia de registro con reintentos
    - **Property 15: Resiliencia de registro con reintentos acotados**
    - **Validates: Requirements 4.7, 8.4**

- [ ] 14. Assessment Service — Evaluaciones (Req 7)
  - [ ] 14.1 Implementar presentación de evaluación y validación de respuestas en servidor
    - `GET /api/v1/evaluaciones/{rutaId}`; `POST .../respuestas` valida tipo, formato y rango antes de calcular; respuesta inválida → rechazo sin puntaje
    - _Requirements: 7.1, 7.6, 7.7_
    - _Properties: 25_
  - [ ] 14.2 Implementar cálculo de puntaje, umbral, reintentos y enfriamiento
    - Puntaje 0–100; aprobado si ≥ umbral (default 70); hasta 3 reintentos; agotados → enfriamiento 24 h y reinicio de contador
    - _Requirements: 7.2, 7.3, 7.4, 7.5_
    - _Properties: 23, 24_
  - [ ]* 14.3 Escribir test de propiedad para puntaje y aprobación
    - **Property 23: Puntaje de evaluación y aprobación**
    - **Validates: Requirements 7.2, 7.3**
  - [ ]* 14.4 Escribir test de propiedad para reintentos y enfriamiento
    - **Property 24: Reintentos de evaluación y enfriamiento**
    - **Validates: Requirements 7.4, 7.5**
  - [ ]* 14.5 Escribir test de propiedad para validación de respuestas en servidor
    - **Property 25: Validación de respuestas de evaluación en servidor**
    - **Validates: Requirements 7.6, 7.7**

- [ ] 15. Certification Service — Certificación (Req 6)
  - [ ] 15.1 Implementar emisión de certificado condicionada e idempotente
    - `POST /api/v1/certificados` emite si ruta completa y puntaje ≥ umbral; rechazo con mensaje si < umbral; idempotencia por (perfil, ruta); formato con fecha ISO-8601 y código 16–64 chars alfanumérico
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
    - _Properties: 19, 20, 21_
  - [ ] 15.2 Implementar consulta de certificado con autorización por titular
    - `GET /api/v1/certificados/{id}`; solo titular; inexistente → mensaje sin filtrar otros perfiles; no titular → error de autorización + registro del intento con solicitante y fecha ISO-8601
    - _Requirements: 6.5, 6.6, 6.7_
    - _Properties: 22_
  - [ ]* 15.3 Escribir test de propiedad para emisión condicionada al umbral
    - **Property 19: Emisión de certificado condicionada al umbral**
    - **Validates: Requirements 6.1, 6.2**
  - [ ]* 15.4 Escribir test de propiedad para formato del certificado
    - **Property 20: Formato del certificado emitido**
    - **Validates: Requirements 6.3**
  - [ ]* 15.5 Escribir test de propiedad para idempotencia de emisión
    - **Property 21: Idempotencia de emisión de certificado**
    - **Validates: Requirements 6.4**

- [ ] 16. Conversion Service — Incentivos y microseguros (Req 5)
  - [ ] 16.1 Implementar entrega de incentivo con reintentos y estado pendiente
    - `POST /api/v1/conversion/incentivos/{rutaId}`; entrega ≤ 5 s con confirmación observable; reintentos ≤ 3 (intervalo ≥ 5 s) conservando completitud; tras 3 fallos → "pendiente" y registro por `profile_id`
    - _Requirements: 5.1, 5.2, 5.3_
    - _Properties: 16_
  - [ ] 16.2 Implementar oferta de microseguros y registro de intención
    - `GET /api/v1/conversion/microseguros` (1–5 por tipo de perfil; sin perfil, el agente lo solicita; sin oferta, informa y registra ausencia con el tipo); `POST /api/v1/conversion/intenciones` idempotente; enmascaramiento de PII en respuestas
    - _Requirements: 5.4, 5.5, 5.6, 5.7, 5.8, 5.9_
    - _Properties: 17, 18_
  - [ ]* 16.3 Escribir test de propiedad para estado de entrega de incentivo
    - **Property 16: Invariante de estado de entrega de incentivo**
    - **Validates: Requirements 5.1, 5.2, 5.3**
  - [ ]* 16.4 Escribir test de propiedad para opciones de microseguro acotadas
    - **Property 17: Opciones de microseguro acotadas y pertinentes**
    - **Validates: Requirements 5.4**

- [ ] 17. Gamification Service — Insignias y puntos (Req 19)
  - [ ] 17.1 Implementar otorgamiento idempotente de insignias y puntos
    - `POST /api/v1/gamificacion/reconocimientos`; otorga al completar microcápsula o ruta (disparado por el Learning Service en tarea 13.3); reglas de otorgamiento ejecutadas exclusivamente en backend; idempotente por `client_event_id` + insignia (no duplica, conserva el registro existente); reintentos ≤ 3 conservando el evento sin pérdida; reconocimiento visible ≤ 5 s; validación de elegibilidad de beneficio sobre microseguro en backend (coordinación con Conversion Service, Tarea 16)
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6_
    - _Properties: 41_
  - [ ] 17.2 Implementar consulta de reconocimientos con autorización por titular
    - `GET /api/v1/gamificacion/reconocimientos`; lista las insignias y el total de puntos del titular autenticado; acceso a reconocimientos ajenos → error de autorización sin exponer PII
    - _Requirements: 19.7, 19.8_
    - _Properties: 42_
  - [ ]* 17.3 Escribir test de propiedad para idempotencia del otorgamiento
    - **Property 41: Idempotencia del otorgamiento de insignias**
    - **Validates: Requirements 19.5**
  - [ ]* 17.4 Escribir test de propiedad para autorización en consulta de reconocimientos
    - **Property 42: Autorización por propiedad en consulta de reconocimientos**
    - **Validates: Requirements 19.7, 19.8**

- [ ] 18. Metrics Service + Tablero ODS (Req 8, Req 15)
  - [x] 18.1 Implementar registro de eventos con asignación de zona idempotente
    - `POST /api/v1/metricas/eventos` con `client_event_id`; tipo, zona (o "sin_zona" no clasificado) y timestamp ISO-8601; reintentos ≤ 3 + cola de pendientes ante fallo
    - _Requirements: 8.1, 8.2, 8.4_
    - _Properties: 15, 26_
  - [x] 18.2 Implementar agregados con k-anonimato y sin PII individual
    - `GET /api/v1/metricas/reportes`; frescura ≤ 60 s; supresión de zonas con < 5 Usuarios; conteo cero + ausencia de datos tras supresión; sin campos identificables
    - _Requirements: 8.3, 8.5, 8.6, 8.7_
    - _Properties: 27, 28_
  - [ ] 18.3 Implementar Tablero de Impacto ODS con autorización de rol
    - `GET /api/v1/impacto/tablero`; solo rol administrativo (verificado en backend); datos agregados/anonimizados vinculados a ODS 8/10/13; servido desde vista precalculada vía Data Operativa (GraphQL)
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7_
    - _Properties: 27, 28_
  - [ ]* 18.4 Escribir test de propiedad para asignación de zona en eventos
    - **Property 26: Asignación de zona en eventos de métrica**
    - **Validates: Requirements 8.1, 8.2**
  - [ ]* 18.5 Escribir test de propiedad para k-anonimato en reportes
    - **Property 27: k-anonimato en reportes agregados**
    - **Validates: Requirements 8.6, 15.4**
  - [ ]* 18.6 Escribir test de propiedad para reportes sin PII individual
    - **Property 28: Reportes sin PII individual**
    - **Validates: Requirements 8.5, 15.3**

- [ ] 19. Survey Service — Encuesta de satisfacción (Req 20)
  - [x] 19.1 Implementar presentación de la encuesta con idempotencia
    - `GET /api/v1/encuestas/{rutaId}`; presenta la encuesta breve y opcional (escala 1–5) solo si no ha sido respondida ni omitida para esa ruta y Usuario; habilitada al completar la Ruta_de_Aprendizaje o hito (enganche con Learning Service); respuesta por texto o voz coherente con voz-first; omitible sin bloquear
    - _Requirements: 20.1, 20.2, 20.6_
    - _Properties: 44_
  - [x] 19.2 Implementar validación en servidor y registro agregado sin PII
    - `POST /api/v1/encuestas/{rutaId}/respuestas`; valida tipo/formato/rango (calificación 1–5) antes de registrar, rechazo indicando campo inválido; registra asociado al Perfil_de_Usuario y zona sin PII en ≤ 5 s; reintentos ≤ 3 conservando la respuesta sin pérdida (coordinación con Metrics Service)
    - _Requirements: 20.3, 20.4, 20.5_
    - _Properties: 43_
  - [~] 19.3 Implementar reporte agregado de satisfacción por zona y retención
    - `GET /api/v1/encuestas/reportes`; agregado por zona con supresión k-anonimato ≥ 5; retención/anonimización de respuestas sensibles ≥ 90 días
    - _Requirements: 20.7, 20.8_
    - Nota: reporte agregado con supresión k-anonimato ≥ 5 implementado. Falta el proceso de retención/anonimización a 90 días (el modelo solo deja la base preparada).
  - [ ]* 19.4 Escribir test de propiedad para validación en servidor de la respuesta
    - **Property 43: Validación en servidor de la respuesta de encuesta**
    - **Validates: Requirements 20.3**
  - [ ]* 19.5 Escribir test de propiedad para idempotencia de presentación/registro
    - **Property 44: Idempotencia de presentación/registro de la encuesta**
    - **Validates: Requirements 20.6**

- [x] 20. Offline Sync Service (Req 18 — backend)
  - [x] 20.1 Implementar sincronización idempotente y fusión de progreso
    - `POST /api/v1/sync/acciones` aplica lote con `client_event_id` (idempotente); resolver conflictos fusionando pasos completados sin pérdida
    - _Requirements: 18.2, 18.4_
    - _Properties: 36, 37_
  - [ ]* 20.2 Escribir test de propiedad para idempotencia de sincronización
    - **Property 36: Idempotencia de la sincronización offline**
    - **Validates: Requirements 18.2**
  - [ ]* 20.3 Escribir test de propiedad para fusión monótona de progreso
    - **Property 37: Fusión monótona de progreso sin pérdida**
    - **Validates: Requirements 18.4**

- [ ] 21. Checkpoint — Verificar servicios de dominio y métricas
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 22. Frontend PWA — Shell, caché offline y detección de red (Req 2, Req 18)
  - [~] 22.1 Implementar shell de la app y estrategias de Service Worker
    - Shell ligero; cache-first para estáticos y microcápsulas descargadas; network-first con timeout para datos dinámicos; fallback sin caché descargando por visita
    - _Requirements: 2.1, 2.4, 2.5, 18.1_
    - Nota: shell y `ngsw-config.json` con estáticos (prefetch/lazy) y API dinámica `freshness` con timeout 3 s listos. Falta el grupo de caché para microcápsulas descargadas (depende del Learning Service, Tarea 13).
  - [~] 22.2 Implementar detección de red, cola local idempotente y precarga
    - Indicador de estado ≤ 2 s tras interrupción ≥ 3 s conservando último paso; cola local con `client_event_id` sincronizada vía Offline Sync; precarga de siguiente microcápsula; estado de sincronización en lenguaje simple
    - _Requirements: 2.8, 2.9, 18.2, 18.3, 18.5_
    - Nota: detección de red (umbral 3 s), indicador de conexión y cola local con `client_event_id` listos. Falta la precarga de la siguiente microcápsula (depende de la Tarea 13).
  - [ ]* 22.3 Escribir test de propiedad (fast-check) para generación de clave de idempotencia de la cola
    - **Property 36: Idempotencia de la sincronización offline** (lógica cliente de la cola)
    - **Validates: Requirements 18.2**

- [ ] 23. Frontend PWA — Autenticación, voz-first y accesibilidad (Req 1, Req 13, Req 14)
  - [x] 23.1 Implementar pantallas de autenticación sin fricción
    - Formulario teléfono + Clave de 4 dígitos; restauración de sesión; mensajes en español coloquial; sin correo ni descargas
    - La pantalla de creación de la Clave muestra un texto de ayuda en español coloquial sugiriendo usar los últimos 4 dígitos de la cédula como pista para recordarla, sin validar la Clave contra la cédula ni almacenar la cédula (solo texto de UI)
    - _Requirements: 1.1, 1.3, 1.4, 1.8, 2.6, 2.7_
  - [~] 23.2 Implementar interacción voz-first y controles accesibles
    - Modo primario por voz con texto alternativo en el mismo flujo; controles de voz ≥ 44×44 px operables con una mano; reproducción TTS; captura y envío de notas de voz
    - _Requirements: 14.1, 14.2, 14.3, 14.4_
    - Nota: control de voz con objetivos táctiles ≥ 44×44 px listo. Faltan la captura real (MediaRecorder), el envío al pipeline STT y la reproducción TTS (dependen de la Tarea 11.4).
  - [ ] 23.3 Implementar flujos de aprendizaje/evaluación/conversión en UI
    - Consumo de endpoints de learning, assessment, certification y conversion; indicador de procesamiento de IA; mínimos pasos de interacción
    - _Requirements: 3.6, 3.7, 13.1_
  - [ ] 23.4 Aplicar conformidad de accesibilidad WCAG 2.1 AA
    - Contraste y tamaños de fuente AA; objetivos táctiles ≥ 44×44 px; operable a 320 px y 3G; textos en español coloquial
    - _Requirements: 13.2, 13.3, 13.5, 13.6_
  - [ ]* 23.5 Escribir pruebas de accesibilidad y performance budget
    - axe-core/Lighthouse para contraste/roles AA y objetivos táctiles; budgets de bundle (≤ 500 KB / ≤ 50 KB) y TTI ≤ 3 s con throttling 3G
    - _Requirements: 2.2, 2.3, 2.4, 13.2, 13.3_

- [ ] 24. Integración y cableado final
  - [ ] 24.1 Cablear API Gateway, headers de seguridad y OpenAPI
    - Enrutar `/api/v1/*` por el gateway con TLS, rate limiting y Correlation-ID; headers HSTS, CSP, nosniff, X-Frame-Options, Referrer-Policy, Permissions-Policy; exponer OpenAPI como contrato
    - _Requirements: 11.1, 12.2_
  - [ ] 24.2 Integrar frontend y backend end-to-end
    - Conectar PWA con todos los servicios de dominio vía gateway; verificar sesión por cookie httpOnly; graceful shutdown
    - _Requirements: 2.1, 12.3_
  - [ ]* 24.3 Escribir pruebas de integración end-to-end con dependencias mockeadas
    - Flujo voz STT → redacción → guardrails → LLM → TTS; SSO WordPress y restauración de sesión; todas las dependencias externas mockeadas
    - _Requirements: 3.1, 10.1, 10.2, 11.5_

- [ ] 25. Checkpoint final — Asegurar cobertura y calidad
  - Ensure all tests pass, ask the user if questions arise. Verificar cobertura ≥ 80% en lógica de negocio, cero issues críticos/bloqueantes (SonarQube) y colecciones Postman por operación en `postmanCollections/`.

## Notes

- Las tareas marcadas con `*` son opcionales (pruebas unitarias, de propiedad, integración, accesibilidad y performance) y pueden omitirse para un MVP más rápido; el núcleo funcional nunca se marca opcional.
- Cada tarea referencia requisitos específicos (`_Requirements:_`) y, cuando aplica, las propiedades de correctitud que valida (`_Properties:_`).
- Las 44 propiedades de correctitud se implementan una por sub-tarea con Hypothesis (backend) o fast-check (frontend), mínimo 100 iteraciones, etiquetadas **Feature: cima-plataforma, Property {n}**.
- Todas las dependencias externas (LLM, STT/TTS, pagos, core de pólizas, GraphQL) se mockean en pruebas; ningún test consume backends reales.
- Los checkpoints aseguran validación incremental en cortes razonables.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1"] },
    { "id": 1, "tasks": ["3.1", "3.2", "3.3", "4.1", "22.1"] },
    { "id": 2, "tasks": ["3.4", "3.5", "4.2", "4.3", "9.1", "22.2"] },
    { "id": 3, "tasks": ["6.1", "7.1", "9.2", "10.1", "10.2", "22.3"] },
    { "id": 4, "tasks": ["6.2", "6.3", "6.4", "7.2", "7.3", "7.4", "10.3", "11.1", "11.2"] },
    { "id": 5, "tasks": ["6.5", "6.6", "6.7", "6.8", "6.9", "7.5", "7.6", "7.7", "7.8", "7.9", "7.10", "7.11", "9.2", "10.4", "10.5", "11.3", "11.4"] },
    { "id": 6, "tasks": ["11.5", "11.6", "13.1", "13.2", "13.3", "14.1", "18.1", "20.1"] },
    { "id": 7, "tasks": ["11.7", "11.8", "11.9", "11.10", "11.11", "11.12", "13.4", "14.2", "15.1", "16.1", "18.2", "20.2", "20.3"] },
    { "id": 8, "tasks": ["13.5", "13.6", "13.7", "13.8", "13.9", "13.10", "14.3", "14.4", "14.5", "15.2", "16.2", "18.3", "19.1", "19.2", "19.3"] },
    { "id": 9, "tasks": ["15.3", "15.4", "15.5", "16.3", "16.4", "17.1", "17.2", "18.4", "18.5", "18.6", "19.4", "19.5"] },
    { "id": 10, "tasks": ["17.3", "17.4", "23.1", "23.2", "23.3", "23.4"] },
    { "id": 11, "tasks": ["23.5", "24.1"] },
    { "id": 12, "tasks": ["24.2"] },
    { "id": 13, "tasks": ["24.3"] }
  ]
}
```
