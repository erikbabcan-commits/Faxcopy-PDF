# Test and verification matrix

Results below are from this task run on 2026-10-17. They describe the exact commands and environment used; they are not claims about GitHub Actions, production, or other platforms.

| Area | Command / method | Result | Notes |
|---|---|---|---|
| Backend unit and integration suite | `cd backend && /tmp/presspilot-venv/bin/python -m pytest -q` | **PASS — 67 passed** | Python 3.12.3 in this runner (project and CI target Python 3.13). One Starlette `TestClient` deprecation warning recommends a future test-client migration. |
| Frontend clean install | `cd frontend && npm ci --ignore-scripts --no-audit --no-fund` | **PASS** | Node 22.23.3; lockfile pins TypeScript 5.8.3. |
| Frontend production build and strict type check | `cd frontend && npm run build && npm run typecheck` | **PASS** | Build output matched committed assets; no runtime frontend dependency. |
| HTTP/API integration smoke | `/tmp/presspilot-venv/bin/python scripts/http_smoke.py` | **PASS — 6 checks** | Real localhost HTTP with API, worker, and private scanner processes; SQLite; synthetic valid, blocked, and corrupt PDFs. Not Docker/PostgreSQL isolation. |
| Browser workflow and responsive checks | `scripts/browser_smoke.py` using Chromium | **PASS — 11 checks** | Real API and worker with synthetic data, including PDF metadata display; 360, 390, 430, and 932 px; no JavaScript errors or horizontal overflow. Temporary screenshots/results were written under `/tmp`, not committed. |
| Compose YAML | `docker compose --env-file .env.example config --quiet` | **PASS** | Configuration validation only. |
| Container image build | `docker compose --env-file .env.example build` | **PASS** | API and scanner images built using Python 3.13 base image and the updated direct dependency pins. |
| Compose/PostgreSQL runtime | `docker compose --env-file .env.example up --build -d` | **BLOCKED — attempted** | The PostgreSQL container became healthy, but the migration container could not resolve Compose hostname `db` (`Temporary failure in name resolution`). Services were stopped without deleting volumes. No successful PostgreSQL migration, API, or worker runtime is claimed. |
| Dependency advisory check | GitHub Advisory Database on pinned direct packages and resolved `opentelemetry-api` | **PASS — no findings for current checked versions** | Found vulnerable original pins for Starlette, python-multipart, pypdf, and cryptography; these were upgraded and the new versions rechecked. This is not a full transitive dependency or base-image audit. |
| GitHub Actions | Recent workflow status | **ACTION REQUIRED** | The new CI run on the Copilot branch awaits approval. The earlier source-import action failed because its token could not create a nested workflow; the importer now excludes workflow files and stages only new validated paths. |
| Vercel deployment | Project/deployment verification | **NOT DEPLOYED** | No connected Vercel project or credentials were available. No URL or deployment ID is claimed. |

## Reproduction

```bash
python -m pip install -r backend/requirements-dev.txt
cd frontend
npm ci --ignore-scripts --no-audit --no-fund
npm run build
npm run typecheck
cd ../backend
python -m pytest -q
cd ..
python scripts/http_smoke.py
python scripts/browser_smoke.py
docker compose --env-file .env.example config --quiet
docker compose --env-file .env.example build
```

The browser smoke requires Playwright Chromium. The Compose runtime result above is not promoted to PASS by the successful config/image-build checks. WCAG AA conformance has not been measured. PostgreSQL behavior, a production reverse proxy, external load/security testing, backups/restores, and live deployment remain unverified.
