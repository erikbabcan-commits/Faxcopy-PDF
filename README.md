# PressPilot / Faxcopy-PDF

PressPilot is a review-first PDF inspection and DTP workflow pilot. It contains a TypeScript browser client, a Python/FastAPI API, a persistent job worker, an isolated scanner service for Docker deployments, and synthetic PDF fixtures.

**Product status:** This repository is not a deployed or production-ready SaaS. The scanner performs conservative structural checks; it is not a certified PDF/X preflight or a print-readiness decision engine. Every report keeps `print_ready=false` and `release_allowed=false`.

## Architecture

- `frontend/`: strict TypeScript client and committed static build (`frontend/dist/`).
- `backend/app/main.py`: FastAPI application, authentication, tenant-scoped endpoints, static client serving.
- `backend/app/worker.py`: durable database-backed queue and report persistence.
- `backend/app/inspector.py`: deterministic PDF structure and geometry inspection.
- `backend/migrations/`: Alembic schema.
- `compose.yaml`: PostgreSQL, API, worker, and private scanner service for a single-host pilot.
- `samples/`: synthetic regression PDFs, including intentionally invalid files.
- `docs/`: architecture, audit, deployment, security, operations, and test information.

The UI and API use the same origin. Vercel can host the static client, but the Python API, database, worker, and scanner require a separate persistent deployment. No live Vercel or backend deployment is configured or verified here; a static-only deployment cannot provide login, uploads, or inspection.

## Local development

Requirements: Python 3.13. Node.js 22 is only needed to rebuild the frontend. Docker Compose is optional.

### Linux / macOS

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python scripts/run_local.py init --workspace "My print shop" --email "admin@example.test"
.venv/bin/python scripts/run_local.py serve
```

### Windows PowerShell

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe scripts\run_local.py init --workspace "My print shop" --email "admin@example.test"
.\.venv\Scripts\python.exe scripts\run_local.py serve
```

Initialization prompts for a password. Open `http://localhost:8080` and use the workspace ID printed by the command. The local launcher binds to loopback and uses a limited subprocess, **not** a full security sandbox; use only trusted test PDFs in this mode.

### Docker pilot

From the repository root, generate a local `.env` and start the services:

```bash
python scripts/make_env.py
docker compose up --build -d
docker compose exec api python -m app.manage bootstrap --workspace "My print shop" --email "admin@example.test"
```

Do not expose the loopback-only API directly to the internet. Back up persistent volumes before maintenance; `docker compose down -v` deletes volumes.

## Build and tests

```bash
cd frontend && npm install --ignore-scripts && npm run build
cd ../backend && python -m pytest -q
cd .. && python scripts/http_smoke.py
```

The CI workflow also runs the Playwright browser smoke test. See [docs/TESTING.md](docs/TESTING.md) for verified results and blocked checks; historical results in the original package are not claims about this environment.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Audit findings](docs/AUDIT.md)
- [Deployment and Vercel constraints](docs/DEPLOYMENT.md)
- [Security controls and remaining risks](docs/SECURITY.md)
- [Test matrix](docs/TESTING.md)
- [Operations guide](docs/OPERATIONS.md)
- [Scope and supported checks](docs/SCOPE.md)

Environment variable templates are in [`.env.example`](.env.example) and [`backend/.env.example`](backend/.env.example). Never put secrets in frontend variables or committed files.
