# PressPilot / Faxcopy PDF — pilot

Python/FastAPI document inspection API, worker and dependency-free TypeScript
browser client. The reviewable source is now in `backend/`, `frontend/`,
`scripts/` and `infra/`; the original versioned ZIP remains unchanged. The MIT
license covers original source; branding and third-party licensing need owner
review before commercialization.

## MacBook Air: local start without Docker

See [the MacBook Air guide](docs/MACBOOK_AIR.md) for Intel / Monterey setup.
With Python 3.12 or 3.13 installed:

```sh
bash scripts/setup_local.sh
bash Start-PressPilot.command
```

Open http://localhost:8080. The setup preserves existing local data and uses
the committed frontend build; Node is only needed when editing the frontend.
Run `bash scripts/setup_local.sh --verify` for disposable backend + HTTP checks.

## Local synthetic reproduction

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements-dev.txt
(cd frontend && npm ci --ignore-scripts && npm run typecheck && npm run build)
(cd backend && python -m pytest -q)
python scripts/browser_smoke.py
```

The browser scenario needs Playwright Chromium (`python -m playwright install
chromium`) and uses generated local accounts, a temporary database and synthetic
PDFs. It is not a production deployment. See [architecture](docs/ARCHITECTURE.md),
[operations](docs/OPERATIONS.md) and [original scope](docs/ORIGINAL_README.md).

## Security and verification limits

PDF preflight is conservative, not malware certification or PDF/X compliance.
Untrusted production uploads require the dedicated resource-limited scanner.
Original verification snapshots and synthetic offline screenshots from v0.1.0
are included under `docs/`. They describe the supplied archive, not the current
branch test results or a deployed service. `MANIFEST.sha256` describes that
original archive; newer parser/CI fixes intentionally differ from its hashes. Resolved Python 3.13/Linux dependency locks and PostgreSQL/storage release gates
are documented in [release gates](docs/RELEASE_GATES.md). Review current audit
and CI evidence before internet exposure.
No production credentials, migrations, deployment or auto-import commit is used.
CI verifies the PR SHA; inspect its actual results rather than assuming green.

## Evidence and reuse boundary

The [change/evidence map](docs/ASKABLE_EVIDENCE.md) identifies specific merged
changes, their test entrypoints and unresolved provenance questions. Git history
and the repository MIT file do **not** by themselves establish who owns every
file in the imported archive or whether a particular change may be supplied
for external AI training. The owner must review the original archive, upstream
attribution and third-party rights before reusing any code outside this project.
