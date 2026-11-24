#!/usr/bin/env bash
# Paso 2 de 2 de la infraestructura de la hackatón (AWS CloudShell, us-east-1).
# Crea la función de rutas, el acceso de CloudFront a S3 (OAC) y la distribución:
# la PWA desde S3 y /api/* hacia el servidor EC2. Usa ~/.cima-hackaton.env del
# paso 1 y no duplica recursos si se vuelve a correr.
#
# Seguridad: solo esta distribución puede leer el bucket, y solo la carpeta app/.
set -euo pipefail
export AWS_DEFAULT_REGION=us-east-1
ESTADO=~/.cima-hackaton.env
AQUI=$(cd "$(dirname "$0")" && pwd)
NOMBRE=cima-hackaton

# `set -a` exporta lo que se lee del estado: distribucion.py lo toma del entorno.
set -a
# shellcheck disable=SC1090
source "$ESTADO"
set +a
: "${BUCKET:?Corra primero infra-1-servidor.sh}" "${INSTANCIA:?Corra primero infra-1-servidor.sh}"
guardar() { echo "$1=$2" >> "$ESTADO"; export "$1=$2"; }
CUENTA=$(aws sts get-caller-identity --query Account --output text)

export ORIGEN
ORIGEN=$(aws ec2 describe-instances --instance-ids "$INSTANCIA" \
  --query 'Reservations[0].Instances[0].PublicDnsName' --output text)
[ -n "$ORIGEN" ] && [ "$ORIGEN" != "None" ] || { echo "El servidor no tiene DNS público."; exit 1; }

# 1. Función que manda las rutas de la PWA a index.html.
if [ -z "${FUNCION_ARN:-}" ]; then
  aws cloudfront create-function --name "$NOMBRE-spa" \
    --function-config 'Comment=CIMA rutas a index.html,Runtime=cloudfront-js-2.0' \
    --function-code "fileb://$AQUI/cloudfront-funcion-spa.js" >/dev/null
  ETAG=$(aws cloudfront describe-function --name "$NOMBRE-spa" --query ETag --output text)
  aws cloudfront publish-function --name "$NOMBRE-spa" --if-match "$ETAG" >/dev/null
  guardar FUNCION_ARN "$(aws cloudfront describe-function --name "$NOMBRE-spa" --stage LIVE \
    --query FunctionSummary.FunctionMetadata.FunctionARN --output text)"
fi
echo "1/3 Función: $NOMBRE-spa"

# 2. Acceso de CloudFront al bucket (OAC).
if [ -z "${OAC:-}" ]; then
  guardar OAC "$(aws cloudfront create-origin-access-control --origin-access-control-config \
    "Name=$NOMBRE-oac,SigningProtocol=sigv4,SigningBehavior=always,OriginAccessControlOriginType=s3" \
    --query OriginAccessControl.Id --output text)"
fi
echo "2/3 OAC: $OAC"

# 3. Distribución, con políticas administradas por AWS buscadas por su nombre.
politica() {
  aws cloudfront "list-$1-policies" --type managed --output text \
    --query "$2List.Items[?$2.$2Config.Name=='$3'].$2.Id"
}
if [ -z "${DISTRIBUCION:-}" ]; then
  export CACHE_OPT CACHE_NO TODO_VISOR CABECERAS
  CACHE_OPT=$(politica cache CachePolicy Managed-CachingOptimized)
  CACHE_NO=$(politica cache CachePolicy Managed-CachingDisabled)
  TODO_VISOR=$(politica origin-request OriginRequestPolicy Managed-AllViewer)
  CABECERAS=$(politica response-headers ResponseHeadersPolicy Managed-SecurityHeadersPolicy)
  python3 "$AQUI/distribucion.py" > /tmp/cima-distribucion.json
  read -r D DOM < <(aws cloudfront create-distribution \
    --distribution-config file:///tmp/cima-distribucion.json \
    --query '[Distribution.Id, Distribution.DomainName]' --output text)
  rm -f /tmp/cima-distribucion.json
  guardar DISTRIBUCION "$D"
  guardar DOMINIO "$DOM"
fi

printf '{"Version":"2012-10-17","Statement":[{"Sid":"SoloCloudFront","Effect":"Allow","Principal":{"Service":"cloudfront.amazonaws.com"},"Action":"s3:GetObject","Resource":"arn:aws:s3:::%s/app/*","Condition":{"StringEquals":{"AWS:SourceArn":"arn:aws:cloudfront::%s:distribution/%s"}}}]}' \
  "$BUCKET" "$CUENTA" "$DISTRIBUCION" > /tmp/cima-bucket.json
aws s3api put-bucket-policy --bucket "$BUCKET" --policy file:///tmp/cima-bucket.json
rm -f /tmp/cima-bucket.json
echo "3/3 CloudFront: $DISTRIBUCION"
echo
echo "Listo. CloudFront tarda de 5 a 10 minutos en activarse."
echo "Dirección de la app: https://$DOMINIO"
