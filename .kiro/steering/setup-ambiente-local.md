---
inclusion: always
---

# Configuración del ambiente local — CIMA

Esta guía indica qué instalar y cómo dejar el proyecto corriendo en una máquina
nueva. Está escrita para que la lea una persona del equipo y también para que
Kiro la use como contexto al ayudar a configurar el entorno.

> Si eres Kiro ayudando a configurar el ambiente: verifica las versiones
> instaladas antes de sugerir comandos, nunca inventes versiones ni pasos, y si
> un prerrequisito falta, indica cómo instalarlo según el sistema operativo de
> la persona. No ejecutes `poetry install` ni `npm install` sin confirmar que la
> persona tiene acceso al repositorio institucional JFrog.

## 1. Prerrequisitos (instalar en este orden)

| Herramienta | Versión objetivo | Para qué | Cómo verificar |
|---|---|---|---|
| Git | 2.x | Clonar y colaborar | `git --version` |
| Python | 3.12+ | Backend (FastAPI) | `python3 --version` |
| Poetry | 1.8+ | Gestor de dependencias del backend | `poetry --version` |
| Node.js | 20 LTS | Frontend (Angular PWA) | `node --version` |
| npm | 10.x+ | Gestor de paquetes del frontend | `npm --version` |
| Angular CLI | 22.x | Servir y construir el frontend | `ng version` |
| PostgreSQL | 15+ | Base de datos | `psql --version` |
| Docker | (opcional) | Levantar PostgreSQL + PgVector fácil | `docker --version` |

### Instalación por sistema operativo

**macOS (con Homebrew):**

```bash
brew install git python@3.12 node@20 postgresql@15
curl -sSL https://install.python-poetry.org | python3 -
npm install -g @angular/cli@22.2.2
```

**Windows:** instalar desde los instaladores oficiales de Git, Python 3.12,
Node 20 LTS y PostgreSQL 15. Luego, en PowerShell:

```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
npm install -g @angular/cli@22.2.2
```

**Linux (Debian/Ubuntu):**

```bash
sudo apt update && sudo apt install -y git python3.12 python3.12-venv nodejs npm postgresql-15
curl -sSL https://install.python-poetry.org | python3 -
npm install -g @angular/cli@22.2.2
```

## 2. Acceso institucional (JFrog)

Las dependencias se descargan del repositorio institucional JFrog, no de los
registros públicos. Antes de instalar:

- **Backend:** configura Poetry para apuntar a JFrog (fuente privada) con tus
  credenciales institucionales.
- **Frontend:** edita `frontend/.npmrc` y reemplaza `<JFROG_HOST>` y `<REPO>`
  por los valores de la organización (pide la URL exacta al líder técnico).

Sin este acceso, `poetry install` y `npm install` fallarán al resolver paquetes.

## 3. Clonar y ubicarse en la rama correcta

```bash
git clone https://github.com/LauraVillan-SB/cima-plataforma.git
cd cima-plataforma
git checkout develop        # nunca se desarrolla directo sobre main
```

El flujo de ramas y PRs está en `CONTRIBUTING.md`. Crea tu rama de trabajo
desde `develop`: `git checkout -b feature/mi-tarea`.

## 4. Base de datos local (PostgreSQL + PgVector)

Opción rápida con Docker:

```bash
docker run --name cima-postgres -e POSTGRES_USER=cima_app \
  -e POSTGRES_PASSWORD=CHANGE_ME -e POSTGRES_DB=cima \
  -p 5432:5432 -d pgvector/pgvector:pg15
```

Si instalaste PostgreSQL de forma nativa, crea la base `cima`, el usuario
`cima_app` y habilita la extensión: `CREATE EXTENSION IF NOT EXISTS vector;`.

## 5. Backend (FastAPI)

```bash
cd backend
cp .env.example .env     # completa los valores locales; NUNCA pongas secretos reales
poetry install           # resuelve desde JFrog (ver paso 2)
poetry run uvicorn app.main:app --reload
```

- Healthcheck: abre http://localhost:8000/api/v1/health → debe responder
  `{"status":"ok","env":"dev"}`.
- Documentación interactiva: http://localhost:8000/docs
- Pruebas: `poetry run pytest`

## 6. Frontend (Angular PWA)

```bash
cd frontend
npm install              # resuelve desde JFrog (ver .npmrc)
npm start                # equivale a: ng serve
```

- App local: http://localhost:4200
- Pruebas: `npm test` (Jest + fast-check)

## 7. Verificación final (checklist)

- [ ] `git branch` muestra que estás en tu rama creada desde `develop`.
- [ ] `GET /api/v1/health` responde `ok`.
- [ ] `poetry run pytest` pasa en verde.
- [ ] El frontend abre en `http://localhost:4200`.
- [ ] `npm test` pasa en verde.

## 8. Versiones exactas del proyecto (referencia)

Backend (`backend/pyproject.toml`): Python 3.12, FastAPI 0.143.0,
SQLAlchemy 2.1.4, Pydantic 2.14.0, Alembic 1.20.0, asyncpg 0.32.0,
pgvector 0.5.1, pytest 9.1.1, hypothesis 6.168.5.

Frontend (`frontend/package.json`): Angular 22.2.2, RxJS 7.8.2,
TypeScript 5.9.2, Jest 30.5.2, fast-check 4.10.2.

> Todas las dependencias están ancladas a versión exacta (sin `^`, `~`, `*`).
> No cambies estas versiones sin acuerdo del equipo.

## 9. Problemas comunes

- **`poetry install` falla al resolver paquetes:** falta configurar el acceso a
  JFrog (paso 2) o no estás en la red/VPN de la organización.
- **`npm install` falla con 404:** `frontend/.npmrc` aún tiene los placeholders
  `<JFROG_HOST>`/`<REPO>` sin reemplazar.
- **El backend no conecta a la base:** revisa `DATABASE_URL` en `backend/.env` y
  que el contenedor/servicio de PostgreSQL esté arriba en el puerto 5432.
- **`ng` no se reconoce:** falta instalar Angular CLI global (paso 1).
