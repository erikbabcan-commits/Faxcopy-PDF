# Faxcopy-PDF / PressPilot — candidate change evidence

**Status:** technical evidence only. No authorization to license project code to
Askable or any other external party is recorded here.

**Baseline checked:** `main` at `9b42a301c6c16d94b07196989d024230dc0053be`
(2026-10-25). Confirm a fresh HEAD before preparing an external task.

| Git reference | Observable change | Reproduction / relevant checks |
| --- | --- | --- |
| [PR #9](https://github.com/erikbabcan-commits/Faxcopy-PDF/pull/9), merge `3de3b0d` | API-key/request boundary in `backend/app/middleware.py`, `backend/app/security.py` and `backend/tests/test_request_boundary.py` | Run backend pytest; inspect the PR diff and negative authorization cases |
| [PR #10](https://github.com/erikbabcan-commits/Faxcopy-PDF/pull/10), merge `b73f8c8` | Release gates, PostgreSQL/preview accounting verification documentation | `docs/RELEASE_GATES.md`, separate disposable PostgreSQL tests |
| [PR #11](https://github.com/erikbabcan-commits/Faxcopy-PDF/pull/11), merge `9b42a30` | Recovery proof in `scripts/recovery_smoke.py` and `docs/RECOVERY_VERIFICATION.md` | Review recovery runbook and disposable recovery smoke checks |
| [PR #12](https://github.com/erikbabcan-commits/Faxcopy-PDF/pull/12), merge `7061e7d` | VPS configuration / deployment checks | `scripts/check_vps_config.py`, `.github/workflows/ci.yml` |

The first-parent merge author is `erikbabcan-commits`, but that metadata does
not establish exclusive authorship, copyright ownership or permission to
relicense code for model training. Import commit `37688ce` came from a versioned
archive; the originating author(s), contribution rights, dependencies and
PressPilot branding must be reviewed separately.

## Commit-level attribution (Git metadata, not legal ownership)

These are **source commits on the merged PR branches**, not merely merge
commits. Their Git `Author` field is `erzo CBXX <erikbabcan@gmail.com>`;
confirm the relationship to the claimant before describing them as *my own*
contributions in an application.

| Source commit | PR | Observed files / purpose |
| --- | --- | --- |
| `fb6da41` | #9 | `backend/app/middleware.py`, `backend/app/security.py`, `backend/tests/test_request_boundary.py`: route scope and hostile request boundaries |
| `b4ff234` | #9 | `backend/tests/test_request_boundary.py`: independent router-path regression |
| `32d65dd` | #10 | CI, dependency locks, PostgreSQL/storage reconciliation and regression tests |
| `6dc129d` | #11 | `scripts/recovery_smoke.py`, recovery instructions and CI proof |
| `df90dc0` | #12 | Opt-in VPS Compose, Caddy configuration, tests and config validation |
| `6294371` | #12 | Separation of VPS and local pilot resources |

To establish an eligible task, select a **specific** change, review the full
parent-to-commit diff and third-party base, document human design/review and
AI assistance, and confirm permissions for its exact files. Passing tests or
owning the GitHub account is not enough.

## Reproduce without production data

Use generated PDFs and disposable local state only. From the repository root:

```sh
python -m pip install -r backend/requirements-dev.lock
(cd backend && python -m pytest -q --ignore=tests/test_postgres_integration.py)
```

PostgreSQL integration fixtures can truncate test tables. Run them only with
the dedicated `PP_TEST_*` disposable database configuration described in
`docs/RELEASE_GATES.md`. Do not use production credentials or data.

## Required owner decisions before task reuse

- [ ] Identify the original authors and provenance of `presspilot-mvp-v0.1.0.zip`.
- [ ] Establish which exact PR diff / files are original work available for relicensing.
- [ ] Check third-party notices, branding and any customer/employer restrictions.
- [ ] Confirm the exact change may be licensed for external AI training.
- [ ] Prepare a separate private task workspace; do not publish the task, fork or solution.

No checklist item is presumed complete because a CI job succeeded.
