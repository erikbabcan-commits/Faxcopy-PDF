# Technical audit

This is a repository-level review of the recovered source, configuration, and available test evidence. It is not a penetration test, PDF-engine certification, or independent compliance assessment.

## System map

| Area | Implementation |
|---|---|
| Frontend | TypeScript 5.8.3, strict compiler options, native DOM/CSS, no runtime framework or external CDN. Build: `cd frontend && npm run build`; output: `frontend/dist/`. |
| API | Python 3.13 / FastAPI application in `backend/app/main.py`. The API also serves the client at `/` and static assets at `/assets`. |
| Validation | Pydantic request/profile schemas; SQLAlchemy models; Alembic migration under `backend/migrations/`. SQLite supports local single-worker use; PostgreSQL is configured for Compose. |
| Authentication | Argon2id password hashing, opaque server-side sessions in HttpOnly/SameSite cookies, Origin and CSRF checks for writes, database-backed login throttling, expiring hashed API keys with narrow scopes. |
| Authorization | Owner/operator/viewer role checks and tenant filtering in API queries. Isolation is application-enforced; PostgreSQL row-level security is not configured. |
| Queue | Database-backed queue with conditional claims, PostgreSQL `SKIP LOCKED`, worker lease/fencing, bounded manual retries, and periodic retention work. Redis is not used. |
| PDF worker | `backend/app/worker.py` processes queued jobs. Compose sends scan requests to a private scanner service with no database or document volume. Local mode uses a limited subprocess, not a complete sandbox. |
| PDF inspection | Strict pypdf parsing; page boxes and geometry; image-placement DPI; font-program presence; color-space inventory; selected active-content markers; encrypted/corrupt-document handling. Reports are fail-closed and do not authorize print release. |
| Storage | Tenant/job directories on a persistent local volume; original bytes are hashed and not rewritten by the inspector. Retention removes job data; crash-orphan reconciliation is not implemented. |
| Optional assistant | Rules-first output; optional operator-configured Ollama receives selected generic findings only. It does not receive PDFs, extracted text, filenames, or customer identifiers. |
| Deployment | Docker Compose describes a single-host API, PostgreSQL, worker, and scanner arrangement. Vercel can serve only the static client unless a separately deployed API is explicitly integrated. No deployment is configured here. |

### API surface

The authenticated API includes `/api/auth/*`, `/api/me`, `/api/stats`, `/api/profiles`, `/api/jobs`, job report/original/preview/review/retry/delete routes, `/api/audit`, `/api/members`, `/api/keys`, and `/api/openapi.json`. Health endpoints are `/healthz` and `/readyz`. The OpenAPI document is exposed only to an authenticated principal.

### Data and processing states

Upload is persisted and queued, then claimed by a worker and finalized as `review`, `blocked`, or `error`. A clean supported-scope result is still `review`, not `PASS`. Job reports include the job and tenant identifiers, source SHA-256, profile identity/version, engine version, timestamp, findings, and final state. A report digest is stored separately. Original files are not modified by inspection.

## Findings by severity

### Critical

- **No confirmed critical vulnerability identified in this source-level review.** This is not evidence of exploit resistance; no independent penetration test has been performed.

### High

- **Not ready for internet-facing production.** No Vercel project, persistent backend, production secrets, deployment URL, database backup/restore exercise, or public service is configured or verified. A Vercel-only static site cannot perform authentication, upload, or PDF processing.
- **Not a professional preflight engine.** Geometric bleed does not prove artwork extends into bleed; font-program presence does not prove glyph correctness; color inventory does not prove color management; PDF/X metadata is not conformance. The UI and API must continue to prevent `PASS`/print-release claims.
- **PDF isolation is deployment-dependent.** The local subprocess resource limits are not a security sandbox. The Compose scanner has stronger process/network/volume boundaries, but those boundaries have not been independently validated against hostile PDFs or host escape.

### Medium

- **Tenant isolation has no database RLS backstop.** Current API queries apply tenant predicates, and tenant-isolation tests exist. A future query regression or compromised application identity could bypass this application-layer control.
- **Dependency supply-chain verification is incomplete.** Direct Python packages are pinned, but there is no complete Python transitive lock or recorded current vulnerability audit. Frontend dependency resolution is not committed as a lockfile.
- **Production database behavior needs runtime verification.** PostgreSQL queue locking, concurrency, migrations, and restore behavior must be tested on the target host; SQLite coverage does not establish PostgreSQL correctness.
- **Operational controls remain external or incomplete.** Configure trusted proxy/IP rate limiting and edge request limits, monitor storage and worker failures, and add orphan-file reconciliation and tested backups before customer use.
- **Retention is not a complete erasure policy.** Job files and records are removed according to configured retention, while audit history and hashes may persist. Establish contractual retention and deletion requirements before onboarding customers.
- **No antivirus, malware-clean verdict, RIP simulation, color proof, or visual bleed verification is implemented.** Active-content markers are a conservative block signal, not malware scanning.

### Low

- **Password-change cookie deletion attributes were inconsistent.** The database already revoked all sessions, but the response omitted the cookie's secure/HttpOnly/SameSite attributes. The response now matches the login/logout cookie policy.
- **The original import automation attempted to stage all repository changes and add a nested workflow.** GitHub rejected the push because the workflow token lacked `workflows` permission. The importer now stages only new validated archive paths, excludes workflows, and is triggered only by archive changes or explicit dispatch.
- **The original report envelope omitted required record identity and timing metadata.** Worker-persisted reports now include job/tenant/profile identity, timestamp, engine version, and final state, including worker-side error results.

## Release decision

**Do not declare this product production-ready or deploy it as a functional SaaS yet.** Prioritize a target-host security review, PostgreSQL/Docker validation, dependency audit and lock strategy, operational backup/restore and retention design, and a persistent backend deployment. Keep all results in review/block/error states until a validated professional preflight workflow is adopted.
