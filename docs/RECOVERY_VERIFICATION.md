# Synthetic recovery evidence

`scripts/recovery_smoke.py` runs only for this repository's disposable GitHub
Actions project `synthetic-faxcopy-ci`. It is a test, not a production backup or
restore utility. It refuses another project/repository and does not accept an
arbitrary database URL. These guards prevent accidental use, not a hostile
operator who controls Docker or the runner environment.

The probe creates a synthetic tenant/job, pauses API and worker writers, captures
`pg_dump -Fc` and the document archive, then resumes writers. Backup bytes and the
temporary test session remain in process memory; they are not uploaded as CI
artifacts or committed. It rejects truncated dump metadata and unsafe archive
paths, links, duplicate members and oversized expanded archives.

Restore uses a new database `presspilot_recovery_ci` and a new temporary data
directory. Existing destinations cause failure; no existing deployment is
overwritten. Restoring with `--clean` is confined to that newly created test DB.
The application then verifies restored session/tenant isolation, original and
preview hashes, report/decision, storage accounting and restricted runtime roles.
The original database/document volume remains intact.

Read the `containers` job log for the exact commit. A successful check proves
this bounded synthetic recovery scenario. It does not verify encrypted off-host
backups, OS ownership/ACL restoration, point-in-time recovery, disaster isolation,
production volumes, recovery-time objectives, load, or resumed worker processing
against the recovered database. Those require an approved target-specific drill.

PR #9 and #10 are merged; inspect current main CI for the actual release
candidate. Production hostname, hosting account, pricing and release/migration
approval remain separate decisions. Do not infer a production URL from CI.
