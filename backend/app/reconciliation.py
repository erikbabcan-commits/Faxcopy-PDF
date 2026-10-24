"""Read-only filesystem/accounting inspection. Never delete or repair data."""
import os
from pathlib import Path
import stat
from sqlalchemy import select
from .config import settings
from .db import session_factory
from .models import Job, Tenant


def reconcile_storage():
    root = settings().data_dir.resolve()
    observed = {}
    unsafe = []
    for folder, dirs, files in os.walk(root, followlinks=False):
        parent = Path(folder)
        for name in list(dirs):
            if (parent / name).is_symlink():
                unsafe.append(str((parent / name).relative_to(root)))
                dirs.remove(name)
        for name in files:
            path = parent / name
            info = path.lstat()
            rel = str(path.relative_to(root))
            if not stat.S_ISREG(info.st_mode):
                unsafe.append(rel)
            else:
                observed[rel] = info.st_size
    expected = {}
    tenants = []
    with session_factory()() as db:
        for job in db.scalars(select(Job).where(Job.purged_at.is_(None))):
            prefix = f"documents/{job.tenant_id}/{job.id}/"
            expected[prefix + "original.pdf"] = job.size_bytes
            if job.preview_size_bytes or job.preview_available:
                expected[prefix + "preview.png"] = job.preview_size_bytes
        for tenant in db.scalars(select(Tenant)):
            prefix = f"documents/{tenant.id}/"
            actual = sum(n for path, n in observed.items() if path.startswith(prefix))
            tenants.append({"tenant_id": tenant.id, "accounted_bytes": tenant.storage_bytes,
                            "observed_bytes": actual, "difference_bytes": actual - tenant.storage_bytes})
    return {"dry_run": True, "unsafe_paths": sorted(unsafe), "tenants": tenants,
            "missing": sorted(set(expected) - set(observed)),
            "untracked": sorted(set(observed) - set(expected)),
            "size_mismatches": [{"path": k, "expected": n, "observed": observed[k]}
                                for k, n in expected.items() if k in observed and observed[k] != n]}
