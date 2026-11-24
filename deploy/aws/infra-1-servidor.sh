#!/usr/bin/env bash
# Paso 1 de 2 de la infraestructura de la hackatón (AWS CloudShell, us-east-1).
# Crea el bucket S3 privado, el rol del servidor, el grupo de seguridad y el
# servidor EC2. Guarda los identificadores en ~/.cima-hackaton.env y, si se
# vuelve a correr, reutiliza lo que ya existe.
#
# Seguridad: bucket no público; el rol solo lee el paquete de despliegue y los
# parámetros /cima/hackaton/*; sin puerto 22 (se entra con SSM); solo CloudFront
# llega al puerto 80; disco cifrado; IMDSv2 obligatorio.
set -euo pipefail
export AWS_DEFAULT_REGION=us-east-1
ESTADO=~/.cima-hackaton.env
AQUI=$(cd "$(dirname "$0")" && pwd)
NOMBRE=cima-hackaton
ROL=$NOMBRE-ec2
TIPO=${TIPO_INSTANCIA:-t3.small}

touch "$ESTADO" && chmod 600 "$ESTADO"
# shellcheck disable=SC1090
source "$ESTADO"
guardar() { echo "$1=$2" >> "$ESTADO"; export "$1=$2"; }

QUIEN=$(aws sts get-caller-identity --query Arn --output text)
[[ "$QUIEN" != *":root" ]] || { echo "Use patricia-admin, no el usuario raíz."; exit 1; }
CUENTA=$(aws sts get-caller-identity --query Account --output text)
echo "Usuario $QUIEN."

# 1. Bucket S3 privado.
if [ -z "${BUCKET:-}" ]; then
  B="$NOMBRE-$CUENTA"
  aws s3api create-bucket --bucket "$B" >/dev/null
  aws s3api put-public-access-block --bucket "$B" --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  guardar BUCKET "$B"
fi
echo "1/4 Bucket: $BUCKET"

# 2. Rol del servidor con el mínimo de permisos.
if ! aws iam get-role --role-name "$ROL" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROL" --assume-role-policy-document \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  aws iam attach-role-policy --role-name "$ROL" \
    --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
fi
printf '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"s3:GetObject","Resource":"arn:aws:s3:::%s/despliegue/*"},{"Effect":"Allow","Action":"ssm:GetParameter","Resource":"arn:aws:ssm:%s:%s:parameter/cima/hackaton/*"}]}' \
  "$BUCKET" "$AWS_DEFAULT_REGION" "$CUENTA" > /tmp/cima-rol.json
aws iam put-role-policy --role-name "$ROL" --policy-name cima-despliegue \
  --policy-document file:///tmp/cima-rol.json
rm -f /tmp/cima-rol.json
if ! aws iam get-instance-profile --instance-profile-name "$ROL" >/dev/null 2>&1; then
  aws iam create-instance-profile --instance-profile-name "$ROL" >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name "$ROL" --role-name "$ROL"
  echo "Esperando a que IAM propague el perfil..."
  sleep 15
fi
echo "2/4 Rol: $ROL"

# 3. Grupo de seguridad: solo CloudFront hacia el puerto 80.
if [ -z "${GRUPO:-}" ]; then
  VPC=$(aws ec2 describe-vpcs --filters Name=is-default,Values=true \
    --query 'Vpcs[0].VpcId' --output text)
  [ "$VPC" != "None" ] || { echo "No hay VPC por defecto: aws ec2 create-default-vpc"; exit 1; }
  LISTA_CF=$(aws ec2 describe-managed-prefix-lists \
    --filters Name=prefix-list-name,Values=com.amazonaws.global.cloudfront.origin-facing \
    --query 'PrefixLists[0].PrefixListId' --output text)
  G=$(aws ec2 create-security-group --group-name "$NOMBRE-origen" --vpc-id "$VPC" \
    --description "CIMA solo CloudFront al puerto 80" --query GroupId --output text)
  aws ec2 authorize-security-group-ingress --group-id "$G" --ip-permissions \
    "IpProtocol=tcp,FromPort=80,ToPort=80,PrefixListIds=[{PrefixListId=$LISTA_CF}]" >/dev/null
  guardar GRUPO "$G"
fi
echo "3/4 Grupo de seguridad: $GRUPO"

# 4. Servidor EC2 (Ubuntu 24.04).
if [ -z "${INSTANCIA:-}" ]; then
  AMI=$(aws ssm get-parameter --query Parameter.Value --output text --name \
    /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id)
  I=$(aws ec2 run-instances --image-id "$AMI" --instance-type "$TIPO" \
    --iam-instance-profile "Name=$ROL" --security-group-ids "$GRUPO" \
    --metadata-options HttpTokens=required,HttpEndpoint=enabled \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":20,"VolumeType":"gp3","Encrypted":true}}]' \
    --user-data "file://$AQUI/servidor-inicio.sh" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NOMBRE}]" \
    --query 'Instances[0].InstanceId' --output text)
  guardar INSTANCIA "$I"
  echo "Esperando a que el servidor arranque..."
  aws ec2 wait instance-running --instance-ids "$INSTANCIA"
fi
echo "4/4 Servidor: $INSTANCIA"
echo "Listo. Siga con: bash infra-2-cloudfront.sh"
