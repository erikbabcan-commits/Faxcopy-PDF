# Release gates and operating boundaries

This branch is stacked on PR #9. Review/merge that security fix before this branch;
do not release the original main. Green tests are evidence for the tested SHA,
not authorization to migrate or deploy an existing installation.

## Dependencies and reproduction

Python 3.13/Linux runtime, PostgreSQL and development dependency closures are
pinned in `backend/requirements-{runtime,postgres,dev}.lock`. The corresponding
`.txt` files describe direct requirements. Regenerate locks in an isolated
environment and validate both dependency consistency and advisories after changes.
Locks pin versions; they do not provide wheel hashes or an OS/PDFium binary audit.

```sh
python -m pip install -r backend/requirements-dev.lock
(cd frontend && npm ci --ignore-scripts && npm run typecheck && npm run build)
(cd backend && python -m pytest -q --ignore=tests/test_postgres_integration.py)
python -m playwright install chromium
python scripts/browser_smoke.py
```

CI separately runs `tests/test_postgres_integration.py` with disposable admin,
migration and runtime URLs. Never point these destructive test fixtures at a
retained database: they truncate test tables. They require explicit `PP_TEST_*`
variables; ordinary local unit runs do not use PostgreSQL.

## Database role provisioning

Fresh local Compose volumes initialize `presspilot_admin`, `presspilot_migrator`
and `presspilot_runtime`. Only the database container receives the bootstrap
administrator password. API and worker use the runtime URL; the one-shot migrate
service uses the migration URL. Runtime has DML privileges, no schema creation,
DDL, role management, database creation or superuser access. This remains
application tenant isolation; database RLS is not implemented.

`infra/postgres-init.sh` is for a **new** database named `presspilot`.
It does not modify existing volumes. Existing installations require backup,
owner-reviewed role provisioning, grants for existing objects and coordinated
credential configuration. Do not rerun the fresh-init script against production.
`scripts/make_env.py` generates three independent database passwords and the
scanner token without printing them or overwriting an existing `.env`.

## Storage and migration

Migration `20261024_preview_bytes` adds a zero-default preview byte count without
reading or modifying files. New previews reserve their size atomically against
the same tenant quota as originals. If no room remains, the inspection report is
retained and the optional preview is omitted. Purging releases both charges.

Existing preview files retain zero accounting until reviewed reconciliation;
do not declare an existing installation ready merely because its migration ran.
Run `python -m app.manage reconcile-storage` using the operator's normal secured
environment. It reports missing, untracked, size-mismatched and symlink paths and
per-tenant physical/accounting differences. It never deletes files or changes
counters. The report is an observation, not an atomic snapshot: pause writers
for a consistent review. Symlinks are not followed. Retain reports privately.

Quota covers originals and committed previews; database files, upload spools,
temporary parser files and crash orphans still require filesystem capacity
monitoring. A crash between file replacement and DB commit can leave a reported
accounting difference. Automatic reconciliation/cleanup is deliberately absent.

## Release approval checklist

- Owner reviews PR #9, then this stacked change and its migration.
- Require the `verify` and `postgres` jobs from `Verify pilot` on the final SHA;
  require a review and block force pushes/deletions on main. These settings are
  proposals; this branch does not change GitHub administration.
- Choose the actual hosting account, EU region, domain, storage and budget.
- Provide an HTTPS reverse proxy, exact APP_ORIGIN, secure cookies and production
  mode. Enforce edge request/concurrency limits and trusted proxy settings.
- Keep PostgreSQL and scanner unexposed; verify scanner egress isolation on the
  actual host. A local protocol test does not prove production firewall isolation.
- Test consistent DB/document backups and restore on a separate installation.
- Monitor disk headroom, reconciliation differences, failed/expired jobs, queue
  latency, worker heartbeat and scanner errors. Alerts need an owner destination.
- Approve the exact release SHA/image digests, migration and rollback procedure.

No production domain is asserted here. A single Linux VM with at least 4 vCPU,
8 GiB RAM and a separately backed-up persistent disk is a proposed starting
topology, not a measured capacity or an ordered service. Final pricing, provider
and domain remain owner decisions. Do not publish only the frontend as a working
API/worker/scanner deployment.

Rollback must not drop the preview accounting column while newer workers run.
Stop writers, preserve a consistent backup, and review any revert as a new
commit. Reverting PR #9 reintroduces a confirmed authorization flaw.
