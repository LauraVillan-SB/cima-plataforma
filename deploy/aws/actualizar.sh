#!/usr/bin/env bash
# Actualiza CIMA en el servidor EC2 de la hackatón. Lo ejecuta publicar.sh por
# SSM (como root), después de dejar el paquete en /opt/cima.
#
# - Genera los secretos la primera vez (aleatorios, solo legibles por root) y los
#   conserva en las siguientes ejecuciones.
# - Lee de SSM Parameter Store (cifrados) la key de Gemini y la Clave de los
#   usuarios de prueba, si existen. Nunca se escriben en el repositorio.
# - Levanta la base y el backend, carga el catálogo y deja listos a Patricia y Rosa.
set -euo pipefail

DIR=/opt/cima
REGION=us-east-1
PARAMS=/cima/hackaton
AWS_CLI=$(command -v aws || echo /snap/bin/aws)
COMPOSE=(docker compose -f "$DIR/deploy/docker-compose.yml" --project-directory "$DIR")

cd "$DIR"
umask 077

leer_parametro() {
  # Devuelve el valor descifrado o vacío si el parámetro no existe.
  "$AWS_CLI" ssm get-parameter --region "$REGION" --name "$PARAMS/$1" \
    --with-decryption --query Parameter.Value --output text 2>/dev/null || true
}

# 1. Contraseña de la base (solo la primera vez).
if [ ! -f .env ]; then
  printf 'POSTGRES_PASSWORD=%s\n' "$(openssl rand -hex 24)" > .env
  echo "Se generó la contraseña de la base."
fi

# 2. Configuración del backend. Se rehace en cada despliegue, pero conserva el
#    secreto de sesión para no cerrar las sesiones abiertas.
SESION=$(grep -s '^SESSION_SECRET=' backend.env | cut -d= -f2- || true)
[ -n "$SESION" ] || SESION=$(openssl rand -hex 32)
GEMINI=$(leer_parametro gemini_api_key)

{
  echo "APP_ENV=dev"
  echo "COOKIE_SECURE=true"
  echo "COOKIE_SAMESITE=lax"
  echo "SESSION_SECRET=$SESION"
  echo "LOG_LEVEL=INFO"
  if [ -n "$GEMINI" ]; then
    echo "HTTP_ALLOWLIST_DOMAINS=sostenibilidadbolivar.com,generativelanguage.googleapis.com"
    echo "CHAT_LLM_PROVIDER=gemini"
    echo "CHAT_STT_PROVIDER=gemini"
    echo "GEMINI_API_KEY=$GEMINI"
    echo "GEMINI_THINKING_LEVEL=low"
  else
    echo "HTTP_ALLOWLIST_DOMAINS=sostenibilidadbolivar.com"
    echo "CHAT_LLM_PROVIDER=respaldo"
    echo "CHAT_STT_PROVIDER=respaldo"
  fi
} > backend.env
unset GEMINI SESION
if grep -q '^CHAT_LLM_PROVIDER=gemini' backend.env; then
  echo "Asistente: Gemini."
else
  echo "Asistente: respuestas de respaldo (no hay key de Gemini en SSM)."
fi

# 3. Base y backend (el backend aplica las migraciones al arrancar).
"${COMPOSE[@]}" up -d --build --remove-orphans

echo "Esperando a que el backend responda..."
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1/api/v1/health >/dev/null 2>&1; then
    break
  fi
  sleep 5
done
curl -fsS http://127.0.0.1/api/v1/health
echo

# 4. Catálogo y usuarios de prueba.
"${COMPOSE[@]}" exec -T backend python -m app.learning.seed

if ! "${COMPOSE[@]}" exec -T backend python -c "import app.dev.usuarios_locales" >/dev/null 2>&1; then
  echo "Esta versión no trae el script de usuarios de prueba (app.dev.usuarios_locales)."
else
  CLAVE=$(leer_parametro clave_demo)
  if [ -n "$CLAVE" ]; then
    "${COMPOSE[@]}" exec -T -e CIMA_CLAVE_DEMO="$CLAVE" backend python -m app.dev.usuarios_locales
  else
    echo "No se crearon los usuarios de prueba: falta $PARAMS/clave_demo en SSM."
  fi
  unset CLAVE
fi

# 5. Limpieza de imágenes viejas para no llenar el disco.
docker image prune -f >/dev/null
echo "Listo."
