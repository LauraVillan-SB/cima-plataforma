# Changelog — feature/auth-clave-validacion-hashing

## [No publicado]

### Agregado
- Se agregó la validación de la Clave de 4 dígitos y los DTOs del Auth Service con allowlist y doble confirmación (`backend/app/auth/dto.py`) (Tarea 7.1, Req 1.1, 1.3, 1.4).
- Se agregó el servicio de hashing de la Clave con sal vía passlib+bcrypt, sin texto plano (`backend/app/auth/password.py`) (Req 1.5).
- Se agregaron pruebas basadas en propiedades (Hypothesis) para la Property 1 (validación de la Clave) y la Property 2 (round-trip de hashing), más pruebas por ejemplo de los DTOs.
- Se ancló la dependencia `bcrypt = "4.0.1"` en `backend/pyproject.toml`, compatible con passlib 1.7.4.
