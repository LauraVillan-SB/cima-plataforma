---
name: revisar-servicio-cima
description: Revisa un servicio de dominio del backend de CIMA (FastAPI) contra los requisitos de seguridad y arquitectura del proyecto antes de abrir un PR. Úsala al crear o modificar un servicio (auth, profile, learning, chat, etc.) para verificar validación en servidor, autorización anti-BOLA, enmascaramiento de PII, manejo de errores, rutas versionadas y trazabilidad con el spec.
metadata:
  autor: Equipo CIMA
  version: 1.0.0
---

# Revisar un servicio de dominio de CIMA

Esta skill verifica que un servicio del backend de CIMA cumpla las reglas del
proyecto antes de abrir un PR a `develop`. Usa como molde el patrón ya
implementado en `backend/app/profile/` (validación → DTO → service → router →
tests).

## Cómo usarla

1. Identifica el servicio a revisar (carpeta `backend/app/<dominio>/`).
2. Recorre el checklist de abajo sección por sección sobre los archivos del
   servicio (`dto.py`, `service.py`, `router.py`, `models.py`, `tests/`).
3. Por cada ítem, marca si cumple. Si algo falla, corrígelo antes del PR y cita
   el requisito del spec afectado.
4. Al final, ejecuta las pruebas y confirma que están en verde.

## Checklist de revisión

### 1. Validación de entrada (en servidor, siempre)
- [ ] Los datos de entrada usan un modelo Pydantic (DTO), no `dict` suelto.
- [ ] El DTO usa `extra="forbid"` para rechazar campos no permitidos (allowlist).
- [ ] Se normaliza la entrada (trim) con `str_strip_whitespace=True` o validadores.
- [ ] Se valida tipo, formato, longitud y rango (ej. teléfono 7–15 dígitos,
      valores contra una allowlist, longitudes máximas).
- _Requisitos típicos: 9.1, 9.2, 9.3, 7.6._

### 2. Autorización por propiedad del recurso (anti-BOLA)
- [ ] Toda operación sobre un recurso de usuario verifica la titularidad contra
      la identidad autenticada (`current_user_id`), nunca confía en IDs del cliente.
- [ ] Las consultas de "lo mío" se anclan al `current_user_id`.
- [ ] Un acceso a recurso ajeno lanza error de autorización (403) y registra el
      intento SIN PII.
- _Requisitos típicos: 6.5, 6.6, 6.7, 9.6._

### 3. Enmascaramiento de PII y DTO de salida
- [ ] Las respuestas usan un DTO con allowlist de campos (nunca el objeto ORM completo).
- [ ] La PII (teléfono, documento, etc.) se enmascara con `mask_value`, dejando a
      lo sumo los últimos 4 caracteres.
- [ ] Ningún log contiene PII, tokens ni secretos (usar `log_event`, que redacta).
- _Requisitos típicos: 5.9, 9.4, 9.5, 11.2._

### 4. Persistencia segura
- [ ] Se usa el ORM con consultas parametrizadas (`select`, `db.get`); nunca SQL
      concatenado ni `.raw()` con entrada sin sanear.
- [ ] La sesión se obtiene vía la dependencia `get_session` de `common/database.py`.
- [ ] Idempotencia donde aplique (`client_event_id` / restricciones UNIQUE).

### 5. Manejo de errores
- [ ] Se usan errores de dominio específicos (`ValidationError`, `NotFoundError`,
      `ForbiddenError`, `RateLimitedError`), no `except Exception` genérico en la lógica.
- [ ] Los mensajes al cliente son genéricos en español coloquial; el detalle va
      solo a logs internos, sin stack trace ni PII.

### 6. Contrato de API
- [ ] Las rutas están versionadas con prefijo `/api/v1/` y en camelCase o minúsculas.
- [ ] Cada endpoint declara `response_model` (el DTO de salida con PII enmascarada).
- [ ] La operación aporta al contrato OpenAPI (tags y descripciones claras).

### 7. Trazabilidad y pruebas
- [ ] El código cita el/los requisito(s) del spec que implementa (ej. `# Req 9.6`).
- [ ] Hay pruebas unitarias y, cuando aplique, property-based (Hypothesis) que
      cubren validación, anti-BOLA y enmascaramiento.
- [ ] Las pruebas pasan: `cd backend && poetry run pytest` (o el runner del equipo).

### 8. Dependencias e higiene
- [ ] No se añadieron dependencias con rangos (`^`, `~`, `*`, `latest`); versión exacta.
- [ ] No hay secretos hardcodeados; la configuración viene de `common/config.py`.
- [ ] Se actualizó el `CHANGELOG.md` (sección `[No publicado]`, en español).

## Salida esperada

Al terminar, entrega un resumen corto: qué cumple, qué se corrigió y con qué
requisito del spec se relaciona cada corrección. Si algo no se puede verificar
(por ejemplo, las pruebas no corren por falta de acceso a JFrog), indícalo
explícitamente en vez de darlo por cumplido.

## Referencia

El patrón de referencia vive en `backend/app/profile/` y las reglas completas en
`.kiro/specs/cima-plataforma/requirements.md` y en los steering del proyecto.
