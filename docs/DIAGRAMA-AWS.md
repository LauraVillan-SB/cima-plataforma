# Diagrama de arquitectura AWS (editable online)

Diagrama de la arquitectura de CIMA en AWS con íconos oficiales de los servicios,
editable y exportable desde el navegador. CIMA es una **plataforma educativa**:
el diagrama **no incluye pasarela de pagos ni core de pólizas** (fuera de alcance).

## Archivo

- `docs/cima-aws-architecture.drawio` — fuente editable (formato draw.io / diagrams.net).

## Cómo abrirlo y editarlo online

1. Entra a **https://app.diagrams.net** (gratuito, en el navegador).
2. **Open Existing Diagram** → selecciona `docs/cima-aws-architecture.drawio`
   (o conéctalo a GitHub: *Device → GitHub* y ábrelo del repo).
3. La librería de íconos de AWS ya viene incluida (panel izquierdo: busca "AWS").

## Cómo exportarlo (PNG/SVG/PDF)

**File → Export as → PNG / SVG / PDF**. Para documentación se recomienda SVG (vectorial).

## Contenido del diagrama

- **Borde:** Usuario (PWA) → CloudFront + S3 y API Gateway (`/api/v1`).
- **VPC:** ECS Fargate (API y Workers), SQS (cola + DLQ), RDS PostgreSQL + PgVector,
  ElastiCache Redis, Secrets Manager/KMS, CloudWatch/X-Ray, NAT Gateway.
- **Dependencias externas por contrato:** Bedrock/LLM, Transcribe (STT), Polly (TTS),
  IdP institucional y WordPress (opcional).

> No aparecen pagos ni core de pólizas porque CIMA solo forma a los usuarios y, a lo sumo,
> registra el interés en un microseguro como dato de impacto. Coherente con
> `docs/ARCHITECTURE-AWS.md`. Los servicios (Fargate, Bedrock, Transcribe/Polly) son
> supuestos por defecto, editables en draw.io si TI/Cloud decide distinto.

## Paso a paso del flujo (cómo leer el diagrama)

Sigue las flechas de izquierda a derecha. Ejemplo: un agricultor abre CIMA y envía
una nota de voz al asistente.

1. **Usuario (PWA móvil).** Usa la app desde el navegador del celular; no instala nada.
2. **CloudFront → S3.** Primero carga la interfaz (pantallas, botones). Esos archivos
   estáticos viven en **S3** y se sirven rápido por **CloudFront** (CDN con caché cercana
   al usuario). Esta rama solo "pinta la pantalla".
3. **Usuario → API Gateway** (flecha `/api/v1`). Cuando el usuario *hace algo* (manda la
   voz, completa una cápsula), la app llama a la API. Todo entra por el **API Gateway**,
   la única puerta: aplica HTTPS/TLS y limita abusos (rate limit).
4. **API Gateway → ECS Fargate (Backend API).** El gateway pasa la petición al **backend**
   (FastAPI en contenedores), donde viven las reglas de negocio.
5. El backend reparte según la tarea:
   - **→ RDS PostgreSQL + PgVector:** guardar/leer datos (perfil, progreso, certificados).
   - **→ ElastiCache (Redis):** sesión del usuario y control de intentos (rápido, temporal).
   - **→ SQS:** si la tarea es pesada (procesar la voz con IA), la encola en vez de hacerla
     al instante.
6. **SQS → ECS Fargate (Workers).** Los **workers** sacan tareas de la cola y las procesan
   en segundo plano (transcribir audio, llamar a la IA, generar la respuesta en voz). Por
   eso el usuario ve "procesando..." y no se queda bloqueado.
7. **Workers → NAT Gateway → dependencias externas.** Cuando los workers necesitan servicios
   de afuera (IA, transcripción, voz), **salen por el NAT Gateway** con la regla
   *egress HTTPS allowlist*: solo HTTPS y solo hacia dominios permitidos (anti-SSRF, R10).

Las flechas **punteadas** son de apoyo, no del flujo principal:
- **Secrets Manager + KMS:** de dónde el backend obtiene contraseñas/claves de forma segura.
- **CloudWatch + X-Ray:** a dónde se envían logs y métricas para monitoreo y trazabilidad.

> En una frase: el usuario entra por el gateway → el backend decide → guarda en base de datos
> o encola el trabajo pesado → los workers procesan y, si hace falta, salen de forma
> controlada a servicios externos.

## Qué son las "Dependencias externas (por contrato)"

Es el recuadro punteado de la derecha. Son servicios que CIMA **usa pero NO construye ni
opera**: existen por fuera, tienen su propio dueño, y CIMA se conecta a ellos mediante una
interfaz acordada (una API). Por eso están fuera de la VPC.

| Dependencia | Para qué sirve |
|---|---|
| **IdP institucional (JWT)** | Sistema de identidad de Seguros Bolívar: valida quién es el usuario y emite los tokens de sesión. CIMA no crea su propio login desde cero. |
| **Amazon Bedrock (LLM) / externo** | El "cerebro" de IA generativa que produce las respuestas del asistente. Puede ser Bedrock o el proveedor de IA institucional. |
| **Transcribe (STT)** | Convierte la **voz a texto** para que la IA entienda lo que dijo el usuario. |
| **Polly (TTS)** | Convierte la respuesta de **texto a voz** para que el asistente le hable al usuario. |
| **WordPress (opcional)** | Sitio web actual de sostenibilidad; CIMA puede integrarse, pero es opcional. |

Idea clave: **CIMA responde por lo que está dentro de la VPC** (su backend, su base de datos).
Las dependencias externas se consumen, pero su funcionamiento interno es responsabilidad de
su proveedor. Si mañana se cambia de proveedor de IA, solo se cambia esa conexión.

> Alineado con el alcance: este recuadro **no incluye pagos ni core de pólizas**. Solo lo
> necesario para formar al usuario (identidad, IA y voz).
