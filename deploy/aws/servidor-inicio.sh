#!/bin/bash
# Arranque del servidor EC2 de la hackatón (user-data, Ubuntu 24.04). Corre una
# sola vez, al crear la máquina. No lleva secretos.
#
# - Docker y Docker Compose desde los repositorios de Ubuntu.
# - AWS CLI (snap) para bajar el paquete de S3 y leer parámetros de SSM.
# - El agente de SSM ya viene en la imagen de Ubuntu: no se abre el puerto 22.
# - 2 GB de swap para que la construcción de la imagen no se quede sin memoria.
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y docker.io docker-compose-v2
systemctl enable --now docker

snap install aws-cli --classic

if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

install -d -m 700 /opt/cima
