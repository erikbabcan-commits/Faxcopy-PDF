# Deployment

## Current deployment state

No Vercel deployment, backend host, deployment ID, public URL, or READY status is configured or verified in this repository. Do not represent the app as a live SaaS. Deployment is blocked until a Vercel project and a separate persistent backend environment are authorized and configured.

## Frontend build and Vercel boundary

The frontend project root is `frontend/`. With Node.js 22 or later, `npm run build` type-checks the TypeScript and writes the static site to `frontend/dist/`.

Vercel can host that static output, but the client calls same-origin `/api/...` endpoints. It does not contain a serverless Python API or an API base-URL configuration. A static-only Vercel deployment therefore cannot log in, upload files, show jobs, or process PDFs. Do not deploy it as a functional product or silently replace unavailable API behavior with demo data.

Before enabling a Vercel preview:

1. Create/select the correct Vercel project and connect this repository with the actual frontend root directory (`frontend`).
2. Set the build command to `npm run build` and output directory to `dist`.
3. Deploy only after a backend URL/proxy architecture is implemented and tested. The backend must not be exposed without authentication, tenant isolation, and HTTPS.
4. Label any static-only preview clearly and explain that server-dependent actions are unavailable. Do not place secrets or customer documents in frontend environment variables.
5. Verify the deployment URL, routing, assets, API connectivity, and logs from the Vercel project before reporting a successful deployment.

There are no Vercel credentials or deployment tools available in this task environment, so no deployment was attempted and no URL is claimed.

## Persistent backend

The Python API, PostgreSQL database, worker, scanner, and customer-file storage require a persistent container host. The included `compose.yaml` is a single-host pilot template, not a high-availability production design.

1. Generate `.env` from the safe template using `python scripts/make_env.py`; keep it out of version control.
2. Set production `APP_ENV=production`, an exact HTTPS `APP_ORIGIN`, `SECURE_COOKIES=true`, a strong scanner token, and a managed PostgreSQL URL.
3. Place an authenticated HTTPS reverse proxy in front of the API. Configure trusted proxy ranges deliberately; do not accept arbitrary forwarded headers.
4. Keep the scanner private, without database credentials, customer volume, or host-published port. Use target-host controls for egress, memory, CPU, process count, and execution time.
5. Run migrations, then provision the first owner interactively. Never add a default production password.
6. Configure encrypted database and document backups, retention/deletion, monitoring, disk-capacity alerts, and a tested restore procedure.
7. Validate `GET /healthz` and `GET /readyz`, then exercise a synthetic upload through a final `review`, `blocked`, or `error` result. Health endpoints do not prove worker/scanner readiness.

See [OPERATIONS.md](OPERATIONS.md) for the operational boundary and [SECURITY.md](SECURITY.md) for release prerequisites.
