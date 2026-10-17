import base64
import hashlib
import io
import logging
from pathlib import Path
import signal
import time
import uuid
from datetime import datetime, timezone
from . import __version__
from PIL import Image
from sqlalchemy import delete, select, update
from .config import settings
from .db import audit, session_factory
from .models import Heartbeat, Job, now
from .schemas import digest
from .scanning import scan, ScanFailure
from .storage import job_dir

log = logging.getLogger("presspilot.worker")
RUNNING = True


def recover_stale() -> int:
    with session_factory()() as db:
        candidates = db.scalars(select(Job).where(Job.status == "processing", Job.lease_until < now())).all()
        changed = 0
        for job in candidates:
            result = db.execute(update(Job).where(Job.id == job.id, Job.status == "processing", Job.lease_until < now())
                .values(status="error", error_code="WORKER_LEASE_EXPIRED", lease_token=None, lease_until=None, completed_at=now()))
            if result.rowcount:
                changed += 1
                audit(db, job.tenant_id, "job.lease_expired", job_id=job.id)
        db.commit()
        return changed


def claim_job():
    with session_factory()() as db:
        query = select(Job).where(Job.status == "queued", Job.deleted_at.is_(None)).order_by(Job.created_at, Job.id).limit(1)
        if db.bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        job = db.scalar(query)
        if not job:
            return None
        token = str(uuid.uuid4())
        result = db.execute(update(Job).where(Job.id == job.id, Job.status == "queued")
            .values(status="processing", lease_token=token, lease_until=now() + settings().scan_timeout_seconds + 45,
                    attempts=Job.attempts + 1))
        if not result.rowcount:
            db.rollback()
            return None
        audit(db, job.tenant_id, "job.started", job_id=job.id)
        db.commit()
        db.refresh(job)
        return job


def validate_result(job, report):
    if report.get("print_ready") is not False or report.get("release_allowed") is not False:
        raise ScanFailure("SCANNER_UNSAFE_RESULT")
    if report.get("file_sha256") != job.sha256:
        raise ScanFailure("SCANNER_HASH_MISMATCH")
    status = report.get("status")
    if status not in ("review", "blocked", "error"):
        raise ScanFailure("SCANNER_INVALID_STATUS")
    if status != "error":
        if report.get("profile_digest") != job.profile_digest:
            raise ScanFailure("SCANNER_PROFILE_MISMATCH")
        findings = report.get("findings")
        if not isinstance(findings, list) or len(findings) > 1000 or not isinstance(report.get("coverage"), dict):
            raise ScanFailure("SCANNER_INVALID_REPORT")
        if any(f.get("severity") not in ("error", "warning", "info") for f in findings):
            raise ScanFailure("SCANNER_INVALID_REPORT")
        if status == "review" and any(f["severity"] == "error" for f in findings):
            raise ScanFailure("SCANNER_UNSAFE_RESULT")
    return status


def process_one() -> bool:
    recover_stale()
    job = claim_job()
    if not job:
        return False
    payload = None
    error = None
    try:
        path = job_dir(job.tenant_id, job.id) / "original.pdf"
        if hashlib.sha256(path.read_bytes()).hexdigest() != job.sha256 or digest(job.profile_snapshot) != job.profile_digest:
            raise ScanFailure("INPUT_INTEGRITY_FAILED")
        payload = scan(path, job.profile_snapshot)
        status = validate_result(job, payload["report"])
        report = payload["report"]
        report.update({
            "job_id": job.id,
            "tenant_id": job.tenant_id,
            "profile_id": job.profile_id,
            "profile_version": job.profile_version,
            "profile_digest": job.profile_digest,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "final_state": status,
        })
        report.setdefault("engine", {"name": "presspilot-basic", "version": "0.1.0"})
    except ScanFailure as exc:
        status, error = "error", str(exc)
    except Exception:
        log.exception("worker_failure job=%s", job.id)
        status, error = "error", "WORKER_FAILED"
    report = payload["report"] if payload else {
        "schema_version": 1,
        "engine": {"name": "presspilot-basic", "version": __version__},
        "file_sha256": job.sha256,
        "profile_digest": job.profile_digest,
        "status": "error",
        "error_code": error or "WORKER_FAILED",
        "print_ready": False,
        "release_allowed": False,
        "coverage": {},
        "summary": {"pages": 0, "errors": 0, "warnings": 0, "info": 0, "image_placements": 0, "fonts": 0, "color_spaces": []},
        "pages": [],
        "images": [],
        "fonts": [],
        "findings": [],
    }
    report.update({
        "job_id": job.id,
        "tenant_id": job.tenant_id,
        "profile_id": job.profile_id,
        "profile_version": job.profile_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "final_state": status,
    })
    report.setdefault("engine", {"name": "presspilot-basic", "version": __version__})
    with session_factory()() as db:
        result = db.execute(update(Job).where(Job.id == job.id, Job.status == "processing", Job.lease_token == job.lease_token,
                    Job.lease_until > now(), Job.deleted_at.is_(None))
                    .values(status=status, completed_at=now(), lease_token=None, lease_until=None))
        if not result.rowcount:
            db.rollback()
            return True  # Stale result is fenced off; no files or reports are overwritten.
        current = db.get(Job, job.id)
        current.report = report
        current.report_digest = digest(current.report) if current.report else None
        current.error_code = error or (current.report or {}).get("error_code")
        current.preview_available = False
        preview = payload.get("preview_base64") if payload else None
        if preview:
            try:
                if len(preview) > 6 * 1024**2:
                    raise ValueError("Preview too large")
                raw = base64.b64decode(preview, validate=True)
                with Image.open(io.BytesIO(raw)) as image:
                    if image.format != "PNG" or image.width * image.height > 2_000_000:
                        raise ValueError("Invalid preview")
                    image.verify()
                destination = job_dir(job.tenant_id, job.id)
                temp = destination / f"{job.lease_token}.png"
                temp.write_bytes(raw)
                temp.replace(destination / "preview.png")
                current.preview_available = True
            except Exception:
                log.warning("preview_rejected job=%s", job.id)
        audit(db, job.tenant_id, "job.completed", job_id=job.id, status=status,
              report_digest=current.report_digest, error_code=current.error_code)
        db.commit()
    return True


def heartbeat(worker_id):
    with session_factory()() as db:
        record = db.get(Heartbeat, worker_id)
        if record:
            record.last_seen = now()
        else:
            db.add(Heartbeat(id=worker_id, last_seen=now()))
        db.execute(delete(Heartbeat).where(Heartbeat.last_seen < now() - 86400))
        db.commit()


def stop(*_):
    global RUNNING
    RUNNING = False


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    worker_id = str(uuid.uuid4())
    last_heartbeat = 0
    last_maintenance = 0
    while RUNNING:
        try:
            if time.monotonic() - last_maintenance > 600:
                from .maintenance import purge_due
                purge_due()
                last_maintenance = time.monotonic()
            if time.monotonic() - last_heartbeat > 10:
                heartbeat(worker_id)
                last_heartbeat = time.monotonic()
            if not process_one():
                time.sleep(settings().worker_poll_seconds)
        except Exception:
            log.exception("worker_iteration_failed")
            time.sleep(3)


if __name__ == "__main__":
    main()
