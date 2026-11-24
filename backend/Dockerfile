# Imagen del backend de CIMA (FastAPI) para el ambiente de la hackatón en AWS.
#
# - Sin secretos: la configuración llega por variables de entorno en el servidor.
# - Las dependencias salen de `pyproject.toml` con su versión exacta (una sola fuente).
# - Imagen base con versión exacta (la misma de Python que se usa en local).
# - Corre con un usuario sin privilegios.
# - Al arrancar aplica las migraciones de Alembic y luego levanta Uvicorn.
FROM python:3.12.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencias de ejecución, con la versión exacta de pyproject.toml (sin las de pruebas).
COPY pyproject.toml ./
RUN python -c "import tomllib; d = tomllib.load(open('pyproject.toml', 'rb'))['tool']['poetry']['dependencies']; print('\n'.join(f'{k}=={v}' for k, v in d.items() if k != 'python'))" > /tmp/requisitos.txt \
    && pip install -r /tmp/requisitos.txt \
    && rm /tmp/requisitos.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

RUN useradd --create-home --uid 10001 cima
USER cima

EXPOSE 8000

# `--proxy-headers`: detrás de CloudFront, para registrar la IP real del visitante.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=*"]
