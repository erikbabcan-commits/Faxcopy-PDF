# PressPilot / Faxcopy PDF — pilot

Python/FastAPI document inspection API, worker and dependency-free TypeScript
browser client. The reviewable source is now in `backend/`, `frontend/`,
`scripts/` and `infra/`; the original versioned ZIP remains unchanged. The MIT
license covers original source; branding and third-party licensing need owner
review before commercialization.

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
Original execution logs/screenshots remain in the historical ZIP and are not
republished as current test evidence. Parser/image pins are upgraded in this PR;
framework advisories still require compatibility review before internet exposure.
No production credentials, migrations, deployment or auto-import commit is used.
CI verifies the PR SHA; inspect its actual results rather than assuming green.
