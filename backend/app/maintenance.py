import logging
import shutil
from sqlalchemy import delete, select, update
from .db import audit, session_factory
from .models import Job, LoginBucket, SessionToken, Tenant, now
from .storage import job_dir

log = logging.getLogger("presspilot.maintenance")


def erase_job(job_id: str, tenant_id: str, actor_id=None) -> bool:
    with session_factory()() as db:
        job = db.scalar(select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id))
        if not job or job.status == "processing":
            return False
        changed = db.execute(update(Job).where(Job.id == job.id, Job.tenant_id == tenant_id,
                    Job.status != "processing", Job.deleted_at.is_(None))
            .values(status="deleted", deleted_at=now(), report=None, preview_available=False,
                    filename="deleted.pdf", order_ref="", decision_note=None))
        if changed.rowcount:
            audit(db, tenant_id, "job.deleted", actor_id=actor_id, job_id=job.id)
        if not changed.rowcount and job.deleted_at is None:
            db.rollback()
            return False  # A worker won the race; never erase an active job.
        db.commit()
        if job.purged_at:
            return True
        try:
            directory = job_dir(tenant_id, job_id)
            if directory.exists():
                shutil.rmtree(directory)
        except OSError:
            log.exception("file_purge_failed job=%s", job_id)
            return False
        result = db.execute(update(Job).where(Job.id == job_id, Job.deleted_at.is_not(None), Job.purged_at.is_(None))
                              .values(purged_at=now()))
        if result.rowcount:
            db.execute(update(Tenant).where(Tenant.id == tenant_id).values(storage_bytes=Tenant.storage_bytes - job.size_bytes))
            audit(db, tenant_id, "job.files_purged", job_id=job_id)
        db.commit()
        return True


def purge_due() -> int:
    targets = []
    with session_factory()() as db:
        for tenant in db.scalars(select(Tenant)).all():
            jobs = db.scalars(select(Job).where(Job.tenant_id == tenant.id, Job.status != "processing",
                Job.purged_at.is_(None), (Job.created_at < now() - tenant.retention_days*86400) | Job.deleted_at.is_not(None)).limit(100)).all()
            targets.extend((job.id, tenant.id) for job in jobs)
        db.execute(delete(SessionToken).where(SessionToken.expires_at < now()))
        db.execute(delete(LoginBucket).where(LoginBucket.reset_at < now() - 86400))
        db.commit()
    return sum(erase_job(job_id, tenant_id) for job_id, tenant_id in targets)
