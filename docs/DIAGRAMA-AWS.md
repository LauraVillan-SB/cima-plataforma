# Diagrama de arquitectura AWS (editable online)

Diagrama de la arquitectura de CIMA en AWS con los íconos oficiales de los servicios,
editable y exportable desde el navegador (sin instalar nada).

## Archivo

- `docs/cima-aws-architecture.drawio` — fuente editable (formato draw.io / diagrams.net).

## Cómo abrirlo y editarlo online

1. Entra a **https://app.diagrams.net** (draw.io, gratuito, en el navegador).
2. Elige **Open Existing Diagram** y selecciona `docs/cima-aws-architecture.drawio`.
   - También puedes conectarlo a GitHub: *Device → GitHub* y abrir el archivo del repo.
3. Edita libremente: la librería de íconos de AWS ya viene incluida
   (busca en el panel izquierdo "AWS" o activa *More Shapes → Networking → AWS 2025/2019*).

## Cómo exportarlo (PNG/SVG/PDF)

En draw.io: **File → Export as → PNG / SVG / PDF**. Para documentación se recomienda
SVG (vectorial, nítido en cualquier zoom) o PNG a 2x.

## Contenido del diagrama

Representa la arquitectura real de CIMA en AWS:

- **Borde:** Usuario (PWA) → CloudFront + S3 (estáticos) y API Gateway (entrada `/api/v1`).
- **VPC:** ECS Fargate (API y Workers), SQS (cola + DLQ), RDS PostgreSQL + PgVector,
  ElastiCache Redis (sesión), Secrets Manager/KMS, CloudWatch/X-Ray, NAT Gateway.
- **Dependencias externas por contrato:** Bedrock/LLM, Transcribe (STT), Polly (TTS),
  IdP institucional, core de pólizas, pasarela de pagos, gateway #323, WordPress.

> Es coherente con `docs/ARCHITECTURE-AWS.md`. Los servicios (ECS Fargate, Bedrock,
> Transcribe/Polly) son supuestos por defecto a validar por TI/Cloud; edítalos en
> draw.io si la decisión final difiere.

## Alternativa como código (opcional)

Si más adelante prefieres el diagrama versionado como código y regenerable, se puede
usar la librería **Diagrams** (Python) para producir el PNG con íconos de AWS desde un
script. draw.io es la opción recomendada para edición visual online.
