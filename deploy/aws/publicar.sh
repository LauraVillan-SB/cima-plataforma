#!/usr/bin/env bash
# Publica una versión de CIMA (AWS CloudShell, us-east-1). Necesita la
# infraestructura creada (infra-1 y infra-2) y el paquete armado en el
# computador con empaquetar.ps1 y subido a CloudShell:
#
#   bash publicar.sh ~/cima-despliegue.zip
#
# 1. Sube la PWA a S3: archivos con hash con caché larga; index.html, el service
#    worker y el manifiesto sin caché, para que se vea la versión nueva.
# 2. Sube el paquete del backend (código, videos y despliegue) a S3.
# 3. Le pide al servidor, por SSM, que lo baje y ejecute actualizar.sh.
# 4. Limpia la caché de CloudFront.
set -euo pipefail
export AWS_DEFAULT_REGION=us-east-1
# shellcheck disable=SC1090
source ~/.cima-hackaton.env
: "${DISTRIBUCION:?Corra primero infra-1-servidor.sh e infra-2-cloudfront.sh}"
ZIP=${1:-$HOME/cima-despliegue.zip}
[ -f "$ZIP" ] || { echo "No encuentro $ZIP. Súbalo con Actions > Upload file."; exit 1; }

TRABAJO=$(mktemp -d)
trap 'rm -rf "$TRABAJO"' EXIT
unzip -q "$ZIP" -d "$TRABAJO"
cd "$TRABAJO"
if [ ! -f app/index.html ] || [ ! -f deploy/actualizar.sh ]; then
  echo "El paquete está incompleto."
  exit 1
fi

# 1. PWA.
SIN_CACHE=(index.html ngsw.json ngsw-worker.js safety-worker.js worker-basic.min.js manifest.webmanifest)
EXCLUIR=()
for f in "${SIN_CACHE[@]}"; do EXCLUIR+=(--exclude "$f"); done
aws s3 sync app/ "s3://$BUCKET/app/" --delete --only-show-errors "${EXCLUIR[@]}" \
  --cache-control 'public,max-age=31536000,immutable'
for f in "${SIN_CACHE[@]}"; do
  if [ -f "app/$f" ]; then
    aws s3 cp "app/$f" "s3://$BUCKET/app/$f" --only-show-errors --cache-control 'no-cache'
  fi
done
echo "1/4 PWA en S3."

# 2. Paquete del backend.
tar -czf despliegue.tgz backend media deploy
aws s3 cp despliegue.tgz "s3://$BUCKET/despliegue/despliegue.tgz" --only-show-errors
echo "2/4 Paquete del backend en S3."

# 3. Actualizar el servidor por SSM (sin SSH).
ESTADO_SSM=$(aws ssm describe-instance-information --output text \
  --filters "Key=InstanceIds,Values=$INSTANCIA" --query 'InstanceInformationList[0].PingStatus')
if [ "$ESTADO_SSM" != "Online" ]; then
  echo "El servidor aún no aparece en SSM ($ESTADO_SSM). Espere unos minutos y vuelva a correrlo."
  exit 1
fi
python3 - "$BUCKET" > parametros.json <<'PY'
import json, sys
bucket = sys.argv[1]
print(json.dumps({"commands": [
    "set -e",
    "AWS=$(command -v aws || echo /snap/bin/aws)",
    f"$AWS s3 cp s3://{bucket}/despliegue/despliegue.tgz /tmp/cima.tgz --only-show-errors",
    "install -d -m 700 /opt/cima",
    "rm -rf /opt/cima/backend /opt/cima/deploy",
    "tar -xzf /tmp/cima.tgz -C /opt/cima && rm /tmp/cima.tgz",
    "bash /opt/cima/deploy/actualizar.sh",
]}))
PY
COMANDO=$(aws ssm send-command --instance-ids "$INSTANCIA" --document-name AWS-RunShellScript \
  --comment "CIMA actualizar" --timeout-seconds 1800 --parameters file://parametros.json \
  --query Command.CommandId --output text)
echo "3/4 Actualizando el servidor (la primera vez tarda varios minutos)..."
while true; do
  sleep 10
  E=$(aws ssm get-command-invocation --command-id "$COMANDO" --instance-id "$INSTANCIA" \
    --query Status --output text 2>/dev/null || echo Pending)
  case "$E" in Pending|InProgress|Delayed) printf '.' ;; *) echo; break ;; esac
done
aws ssm get-command-invocation --command-id "$COMANDO" --instance-id "$INSTANCIA" \
  --query StandardOutputContent --output text | tail -n 25
if [ "$E" != "Success" ]; then
  echo "El servidor respondió: $E. Errores:"
  aws ssm get-command-invocation --command-id "$COMANDO" --instance-id "$INSTANCIA" \
    --query StandardErrorContent --output text | tail -n 25
  exit 1
fi

# 4. Caché de CloudFront.
aws cloudfront create-invalidation --distribution-id "$DISTRIBUCION" --paths '/*' >/dev/null
echo "4/4 Caché de CloudFront limpia."
echo
echo "Publicado: https://$DOMINIO"
