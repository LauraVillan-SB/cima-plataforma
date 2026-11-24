# Despliegue de CIMA en AWS (ambiente de la hackatón)

Ambiente de **desarrollo** en una cuenta personal de AWS, con el plan gratuito y
**solo datos ficticios** (Patricia y Rosa). No es el ambiente oficial: ese será el
garden corporativo.

## Arquitectura

| Servicio | Para qué |
|---|---|
| **CloudFront** | Dirección única con HTTPS. `/api/*` va al servidor; lo demás, a S3. Así la sesión (cookies `HttpOnly`, `Secure`, `SameSite`) funciona sin CORS. Agrega cabeceras de seguridad. |
| **S3** | La PWA compilada (carpeta `app/`) y el paquete de despliegue (`despliegue/`). Bucket privado: solo CloudFront lee `app/`, con OAC. |
| **EC2** | Un servidor Ubuntu 24.04 (`t3.small`) con Docker: el backend (FastAPI) y PostgreSQL 15 con pgvector. Solo recibe tráfico de CloudFront en el puerto 80; no tiene SSH. |
| **SSM** | Se entra al servidor y se lo actualiza con Systems Manager. Parameter Store guarda cifradas la Clave de prueba y la key de Gemini. |

Los videos propios viajan en el paquete y los sirve el backend con la sesión, como en local.

Limitación conocida: entre CloudFront y el servidor el tráfico va por HTTP (el visitante
siempre usa HTTPS). El grupo de seguridad solo deja entrar a CloudFront. Para el garden,
el origen debe ir con TLS o en una red privada.

## Archivos

| Archivo | Dónde corre | Qué hace |
|---|---|---|
| `empaquetar.ps1` | Tu computador | Compila la PWA y arma `cima-despliegue.zip` en el Escritorio |
| `infra-1-servidor.sh` | CloudShell, una vez | Bucket, rol del servidor, grupo de seguridad y servidor EC2 |
| `infra-2-cloudfront.sh` | CloudShell, una vez | Función de rutas, OAC y distribución de CloudFront |
| `publicar.sh` | CloudShell, en cada versión | Sube la PWA y el paquete, actualiza el servidor y limpia la caché |
| `servidor-inicio.sh` | EC2, al crearlo | Instala Docker, Compose y la AWS CLI; crea swap |
| `actualizar.sh` | EC2, en cada versión | Genera secretos, levanta los servicios, carga el catálogo y los usuarios |
| `docker-compose.yml` | EC2 | Base de datos y backend |
| `distribucion.py`, `cloudfront-funcion-spa.js` | CloudShell | Configuración de CloudFront |

## Paso a paso

### 1. Armar el paquete (tu computador)

```powershell
cd C:\Users\<usuario>\Desktop\Lab-AWS\Cima
powershell -ExecutionPolicy Bypass -File deploy\aws\empaquetar.ps1
```

Queda `cima-despliegue.zip` en el Escritorio.

### 2. Subirlo a CloudShell

1. Entra a la consola con `patricia-admin` (no con el usuario raíz), región **us-east-1**.
2. Abre CloudShell (`>_`). Menú **Actions → Upload file** y escoge `cima-despliegue.zip`.
3. Descomprímelo:

```bash
rm -rf ~/cima && mkdir ~/cima && unzip -q ~/cima-despliegue.zip -d ~/cima && cd ~/cima/deploy
```

### 3. Guardar los secretos en Parameter Store (una vez)

La Clave de 4 dígitos de Patricia y Rosa (escríbela cuando la pida; no se ve ni queda
en el historial):

```bash
read -rsp "Clave de prueba (4 dígitos): " C && echo && \
aws ssm put-parameter --name /cima/hackaton/clave_demo --type SecureString --value "$C" --overwrite && unset C
```

Opcional, para que el asistente responda con Gemini. Sin este parámetro responde con los
mensajes de respaldo:

```bash
read -rsp "Key de Gemini: " K && echo && \
aws ssm put-parameter --name /cima/hackaton/gemini_api_key --type SecureString --value "$K" --overwrite && unset K
```

### 4. Crear la infraestructura (una vez)

```bash
bash infra-1-servidor.sh
bash infra-2-cloudfront.sh
```

El segundo imprime la dirección de la app (`https://xxxx.cloudfront.net`). CloudFront tarda
de 5 a 10 minutos en activarse, y el servidor unos 3 minutos en instalar Docker.

### 5. Publicar

```bash
bash publicar.sh ~/cima-despliegue.zip
```

La primera vez tarda de 5 a 10 minutos, porque el servidor construye la imagen. Si dice
que el servidor no aparece en SSM, espera dos minutos y vuelve a correrlo.

### 6. Probar

Abre la dirección de CloudFront en el celular o en el computador:

- Patricia: celular `3000000001`.
- Rosa Ruiz: celular `3000000002`.
- Clave: la que guardaste en el paso 3.

### Publicar una versión nueva

Repite el paso 1 en tu computador, sube el zip (paso 2, solo el upload) y corre
`bash ~/cima/deploy/publicar.sh ~/cima-despliegue.zip`.

## Costos y cómo apagarlo

Todo cabe en los créditos del plan gratuito. Lo que más consume es el servidor
(`t3.small`). Después de la demo, apágalo para no gastar créditos:

```bash
source ~/.cima-hackaton.env
aws ec2 stop-instances --instance-ids "$INSTANCIA"     # apagar
aws ec2 start-instances --instance-ids "$INSTANCIA"    # volver a prender
```

Al prenderlo cambia su nombre DNS público: hay que actualizar el origen `ec2-api` en
CloudFront (o pedir ayuda para dejarle una IP elástica).

## Seguridad

- Sin secretos en el repositorio ni en el paquete: la contraseña de la base y el secreto
  de sesión se generan en el servidor (solo los lee root); la Clave de prueba y la key de
  Gemini viven cifradas en Parameter Store.
- El rol del servidor solo puede leer `s3://<bucket>/despliegue/*` y los parámetros
  `/cima/hackaton/*`.
- Sin SSH: puerto 22 cerrado; administración por SSM. IMDSv2 obligatorio. Disco cifrado.
- Bucket privado con acceso público bloqueado; CloudFront lo lee con OAC.
- Imágenes base con versión exacta: `python:3.12.10-slim` y pgvector fijado por digest.
- `APP_ENV=dev`: es un ambiente de desarrollo con datos ficticios. No subir datos reales.
