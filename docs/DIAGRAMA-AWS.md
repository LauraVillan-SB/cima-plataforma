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
