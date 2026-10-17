# Security

## Existing controls

- Opaque server-side sessions; Argon2id password hashes; HttpOnly, SameSite cookies; CSRF token and exact Origin validation for writes.
- Database-backed login rate limiting; request-size limits; Pydantic validation; expiring/revocable API keys stored as hashes and constrained by scope.
- Owner/operator/viewer authorization; tenant-scoped object lookups; uploaded filenames are sanitized and storage paths are built from validated identifiers.
- Upload size, extension, MIME, and PDF signature checks; the original is hashed and retained unchanged. Files are served only behind authenticated endpoints.
- Security response headers include CSP, frame denial, no-sniff, referrer policy, and no-store for API responses. Production settings require HTTPS, secure cookies, PostgreSQL, and a configured private scanner.
- Compose runs the scanner as a non-root process without the database network or document volume, with resource limits and no host-published port.
- PDF parse and traversal limits fail to `error`; encrypted, corrupt, and selected active-content documents do not silently pass.

These controls reduce risk but do not establish that the application, deployment, dependencies, container runtime, or host is secure.

## Required before customer data

1. Perform an independent security review and hostile-PDF testing of the exact deployed image and host.
2. Verify PostgreSQL roles, migration/runtime privilege separation, backup encryption, restore, and deletion semantics.
3. Configure HTTPS, a trusted reverse proxy, edge rate limits, upload timeouts, scanner isolation, egress restrictions, and alerting.
4. Lock and audit the full dependency graph and base images; apply updates with regression testing.
5. Define customer-data retention, audit-log retention, incident response, access review, and backup destruction policies.
6. Ensure no frontend build contains server secrets. Do not send customer documents to external AI providers; the optional Ollama adapter receives only selected technical findings.

## Known limitations

- Tenant isolation is enforced in application queries; database row-level security is not configured.
- The local scanner subprocess is not a full sandbox. Compose isolation is a configuration boundary, not proof against parser or host vulnerabilities.
- There is no antivirus or malware-clean guarantee, professional PDF/X conformance engine, RIP/color proof, or visual bleed verification.
- Audit events are operational records, not immutable WORM evidence. Hashes and selected audit metadata can outlive document deletion.
- Automated orphan-file reconciliation, external security testing, production deployment, and restore testing are not verified.

Never publish uploaded PDFs through a public static bucket or expose scanner endpoints. Keep any static-only Vercel build labeled as non-functional preview until an authenticated backend is connected.
