from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
import hashlib
import logging
import os
from pathlib import Path
import re
import secrets
import shutil
import uuid
import httpx
from fastapi import FastAPI, Depends, File, Form, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError
from . import __version__
from .config import settings
from .db import audit, get_db, session_factory
from .maintenance import erase_job
from .middleware import BodyLimitMiddleware, SecurityHeadersMiddleware
from .models import ApiKey, Audit, Heartbeat, Job, Profile, SessionToken, Tenant, User, now, uid
from .schemas import KeyIn, LoginIn, MemberIn, PasswordIn, ProfileIn, ReviewIn, digest
from .security import COOKIE, DUMMY_HASH, check_origin, current, hasher, login_rate_limit, new_session, operator, owner, token_hash, verify_password
from .storage import job_dir, safe_name

log = logging.getLogger("presspilot.api")


@asynccontextmanager
async def lifespan(_):
    os.umask(0o077)
    settings().data_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="PressPilot API", version=__version__, docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.add_middleware(BodyLimitMiddleware, max_bytes=settings().max_upload_mb * 1024**2 + 256*1024)
app.add_middleware(SecurityHeadersMiddleware, secure=settings().secure_cookies)


@app.exception_handler(RequestValidationError)
async def validation_error(_, exc):
    return JSONResponse(status_code=422, content={"detail": "Skontrolujte zadané hodnoty.",
        "errors": [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]})


@app.exception_handler(Exception)
async def unexpected(request: Request, exc):
    request_id = getattr(request.state, "request_id", "unknown")
    log.error("api_failure request_id=%s type=%s", request_id, type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Interná chyba. Kontaktujte správcu s identifikátorom požiadavky.", "request_id": request_id})


def profile_json(p):
    return {"id": p.id, "name": p.name, "version": p.version, "family_id": p.family_id, "rules": p.rules, "digest": p.digest, "created_at": p.created_at}


def member_json(u):
    return {"id": u.id, "email": u.email, "role": u.role, "active": u.active, "created_at": u.created_at}


def job_json(j, detail=False):
    data = {"id": j.id, "filename": j.filename, "order_ref": j.order_ref, "size_bytes": j.size_bytes, "sha256": j.sha256,
            "profile_id": j.profile_id, "profile_name": j.profile_name, "profile_version": j.profile_version,
            "status": j.status, "decision": j.decision, "created_at": j.created_at, "completed_at": j.completed_at,
            "summary": (j.report or {}).get("summary"), "error_code": j.error_code,
            "preview_available": j.preview_available, "attempts": j.attempts}
    if detail:
        data.update(report=j.report, profile_snapshot=j.profile_snapshot, profile_digest=j.profile_digest,
                    report_digest=j.report_digest, decision_note=j.decision_note, reviewer_id=j.reviewer_id, reviewed_at=j.reviewed_at)
    return data


def scoped_job(db, tenant_id, job_id):
    job = db.scalar(select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id, Job.deleted_at.is_(None)))
    if not job:
        raise HTTPException(404, "Zákazka sa nenašla.")
    return job


@app.get("/healthz")
def health():
    return {"status": "ok", "version": __version__}


@app.get("/readyz")
def ready(db=Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db.scalar(select(Tenant.id).limit(1))
        return {"status": "ready"}
    except Exception:
        raise HTTPException(503, "Databáza nie je pripravená. Skontrolujte migrácie.")


@app.post("/api/auth/login")
def login(payload: LoginIn, request: Request, response: Response, db=Depends(get_db)):
    check_origin(request)
    email = payload.email.strip().lower()
    ip = request.client.host if request.client else "unknown"
    login_rate_limit(db, "login-ip:" + ip)
    login_rate_limit(db, f"login-account:{payload.workspace_id}:{email}")
    user = db.scalar(select(User).where(User.tenant_id == payload.workspace_id, User.email == email))
    valid = verify_password(user.password_hash if user else DUMMY_HASH, payload.password)
    if not valid or not user or not user.active:
        raise HTTPException(401, "Nesprávne pracovisko, e-mail alebo heslo.")
    if hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hasher.hash(payload.password)
    old_cookie = request.cookies.get(COOKIE)
    if old_cookie:
        db.execute(delete(SessionToken).where(SessionToken.token_hash == token_hash(old_cookie)))
    raw, session = new_session(db, user)
    audit(db, user.tenant_id, "auth.login", actor_id=user.id)
    db.commit()
    response.set_cookie(COOKIE, raw, httponly=True, secure=settings().secure_cookies, samesite="strict", path="/", max_age=settings().session_ttl_seconds)
    return {"user": member_json(user), "csrf_token": session.csrf_token}


@app.post("/api/auth/logout")
def logout(response: Response, principal=Depends(current), db=Depends(get_db)):
    if principal.session:
        db.execute(delete(SessionToken).where(SessionToken.token_hash == principal.session.token_hash))
    audit(db, principal.user.tenant_id, "auth.logout", actor_id=principal.user.id)
    db.commit()
    response.delete_cookie(COOKIE, path="/", secure=settings().secure_cookies, httponly=True, samesite="strict")
    return {"ok": True}


@app.get("/api/me")
def me(principal=Depends(current), db=Depends(get_db)):
    tenant = db.get(Tenant, principal.user.tenant_id)
    return {"user": member_json(principal.user), "workspace": {"id": tenant.id, "name": tenant.name, "plan": tenant.plan,
        "retention_days": tenant.retention_days}, "csrf_token": principal.session.csrf_token,
        "capabilities": {"professional_preflight": False, "automatic_fixes": False, "automatic_print_release": False,
                         "assistant_mode": "ollama" if settings().llm_base_url and settings().llm_model else "rules",
                         "max_upload_mb": settings().max_upload_mb, "version": __version__}}


@app.post("/api/auth/password")
def change_password(payload: PasswordIn, response: Response, principal=Depends(current), db=Depends(get_db)):
    login_rate_limit(db, "password:" + principal.user.id)
    user = db.get(User, principal.user.id)
    if not verify_password(user.password_hash, payload.old_password):
        raise HTTPException(400, "Aktuálne heslo nie je správne.")
    user.password_hash = hasher.hash(payload.new_password)
    db.execute(delete(SessionToken).where(SessionToken.user_id == user.id))
    audit(db, user.tenant_id, "auth.password_changed", actor_id=user.id)
    db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True, "detail": "Heslo bolo zmenené. Prihláste sa znova."}


@app.get("/api/stats")
def stats(principal=Depends(current), db=Depends(get_db)):
    tid = principal.user.tenant_id
    scope = (Job.tenant_id == tid, Job.deleted_at.is_(None))
    counts = dict(db.execute(select(Job.status, func.count()).where(*scope).group_by(Job.status)).all())
    accepted = db.scalar(select(func.count()).select_from(Job).where(*scope, Job.decision == "accepted"))
    pending = db.scalar(select(func.count()).select_from(Job).where(*scope, Job.status == "review", Job.decision.is_(None)))
    tenant = db.get(Tenant, tid)
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    days = []
    for offset in range(6, -1, -1):
        date = datetime.now(timezone.utc).date() - timedelta(days=offset)
        start = int(datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc).timestamp())
        count = db.scalar(select(func.count()).select_from(Job).where(*scope, Job.created_at >= start, Job.created_at < start + 86400))
        days.append({"date": str(date), "count": count})
    live_workers = db.scalar(select(func.count()).select_from(Heartbeat).where(Heartbeat.last_seen >= now()-120))
    return {"total": sum(counts.values()), "by_status": counts, "accepted": accepted, "pending_review": pending,
            "daily": days, "worker_online": live_workers > 0,
            "usage": {"month": month, "uploads": tenant.monthly_uploads if tenant.quota_month == month else 0,
                      "monthly_limit": tenant.monthly_limit, "storage_bytes": tenant.storage_bytes, "storage_limit_bytes": tenant.storage_limit_bytes}}


@app.get("/api/profiles")
def profiles(principal=Depends(current), db=Depends(get_db)):
    records = db.scalars(select(Profile).where(Profile.tenant_id == principal.user.tenant_id).order_by(Profile.name, Profile.version.desc())).all()
    return [profile_json(p) for p in records]


@app.post("/api/profiles", status_code=201)
def create_profile(payload: ProfileIn, principal=Depends(owner), db=Depends(get_db)):
    tid = principal.user.tenant_id
    db.scalar(select(Tenant).where(Tenant.id == tid).with_for_update())
    if db.scalar(select(func.count()).select_from(Profile).where(Profile.tenant_id == tid)) >= 200:
        raise HTTPException(409, "Dosiahnutý limit 200 verzií profilov.")
    family_id, version_no = uid(), 1
    if payload.base_profile_id:
        base = db.scalar(select(Profile).where(Profile.id == payload.base_profile_id, Profile.tenant_id == tid))
        if not base:
            raise HTTPException(404, "Východiskový profil sa nenašiel.")
        family_id = base.family_id
        version_no = db.scalar(select(func.max(Profile.version)).where(Profile.tenant_id == tid, Profile.family_id == family_id)) + 1
    rules = payload.rules.model_dump()
    record = Profile(tenant_id=tid, name=payload.name.strip(), family_id=family_id, version=version_no, rules=rules, digest=digest(rules))
    db.add(record)
    try:
        db.flush()
        audit(db, tid, "profile.created", actor_id=principal.user.id, profile_id=record.id, version=version_no, digest=record.digest)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Súbežne vznikla nová verzia. Obnovte profily.")
    return profile_json(record)


@app.get("/api/jobs")
def jobs(q: str = Query(default="", max_length=100), status: str = Query(default="", max_length=20),
         limit: int = Query(default=25, ge=1, le=100), offset: int = Query(default=0, ge=0), principal=Depends(current), db=Depends(get_db)):
    scope = [Job.tenant_id == principal.user.tenant_id, Job.deleted_at.is_(None)]
    if q:
        scope.append(Job.filename.contains(q, autoescape=True) | Job.order_ref.contains(q, autoescape=True))
    if status:
        if status not in ("queued", "processing", "review", "blocked", "error", "accepted", "rejected"):
            raise HTTPException(422, "Neplatný filter stavu.")
        scope.append(Job.decision == status if status in ("accepted", "rejected") else Job.status == status)
    total = db.scalar(select(func.count()).select_from(Job).where(*scope))
    records = db.scalars(select(Job).where(*scope).order_by(Job.created_at.desc(), Job.id.desc()).offset(offset).limit(limit)).all()
    return {"items": [job_json(j) for j in records], "total": total, "offset": offset, "limit": limit}


@app.post("/api/jobs", status_code=201)
def upload_job(response: Response, file: UploadFile = File(...), profile_id: str = Form(...),
        order_ref: str = Form(default="", max_length=100), idempotency_key: str = Header(default=""),
        principal=Depends(operator), db=Depends(get_db)):
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", idempotency_key):
        raise HTTPException(422, "Vyžaduje sa Idempotency-Key s dĺžkou 8–80 znakov.")
    tid = principal.user.tenant_id
    profile = db.scalar(select(Profile).where(Profile.id == profile_id, Profile.tenant_id == tid))
    if not profile:
        raise HTTPException(404, "Výrobný profil sa nenašiel.")
    name = safe_name(file.filename or "document.pdf")
    if not name.lower().endswith(".pdf") or file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(415, "Nahrajte súbor PDF.")
    job_id = uid()
    incoming = settings().data_dir.resolve() / ".incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    temp = incoming / f"{job_id}.part"
    destination = None
    size = 0
    sha = hashlib.sha256()
    try:
        with temp.open("xb") as output:
            first = True
            while chunk := file.file.read(1024**2):
                if first and not chunk.startswith(b"%PDF-"):
                    raise HTTPException(415, "Súbor nemá platnú hlavičku PDF.")
                first = False
                size += len(chunk)
                if size > settings().max_upload_mb * 1024**2:
                    raise HTTPException(413, "PDF prekročilo povolenú veľkosť.")
                sha.update(chunk)
                output.write(chunk)
            if size == 0:
                raise HTTPException(415, "Súbor je prázdny.")
            output.flush()
            os.fsync(output.fileno())
        checksum = sha.hexdigest()
        existing = db.scalar(select(Job).where(Job.tenant_id == tid, Job.idempotency_key == idempotency_key))
        if existing:
            if existing.deleted_at or existing.sha256 != checksum or existing.profile_id != profile.id or existing.order_ref != order_ref or existing.filename != name:
                raise HTTPException(409, "Tento idempotentný kľúč už patrí inej požiadavke.")
            response.status_code = 200
            return job_json(existing)
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        db.execute(update(Tenant).where(Tenant.id == tid, Tenant.quota_month != month).values(quota_month=month, monthly_uploads=0))
        reserved = db.execute(update(Tenant).where(Tenant.id == tid, Tenant.monthly_uploads < Tenant.monthly_limit,
                         Tenant.storage_bytes + size <= Tenant.storage_limit_bytes)
            .values(monthly_uploads=Tenant.monthly_uploads + 1, storage_bytes=Tenant.storage_bytes + size))
        if not reserved.rowcount:
            raise HTTPException(429, "Pracovisko dosiahlo mesačný alebo úložný limit.")
        record = Job(id=job_id, tenant_id=tid, creator_id=principal.user.id, idempotency_key=idempotency_key,
            order_ref=order_ref, filename=name, size_bytes=size, sha256=checksum, profile_id=profile.id,
            profile_snapshot=profile.rules, profile_digest=profile.digest, profile_name=profile.name, profile_version=profile.version)
        destination = job_dir(tid, job_id)
        destination.mkdir(parents=True, exist_ok=False)
        temp.replace(destination / "original.pdf")
        (destination / "original.pdf").chmod(0o440)
        db.add(record)
        db.flush()
        audit(db, tid, "job.uploaded", actor_id=principal.user.id, job_id=job_id, sha256=checksum, size_bytes=size, profile_digest=profile.digest)
        db.commit()
        return job_json(record)
    except IntegrityError:
        db.rollback()
        if destination:
            shutil.rmtree(destination, ignore_errors=True)
        raise HTTPException(409, "Duplicitná požiadavka. Obnovte zoznam zákaziek.")
    except Exception:
        db.rollback()
        if destination:
            shutil.rmtree(destination, ignore_errors=True)
        raise
    finally:
        temp.unlink(missing_ok=True)
        file.file.close()


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: str, principal=Depends(current), db=Depends(get_db)):
    return job_json(scoped_job(db, principal.user.tenant_id, job_id), detail=True)


@app.get("/api/jobs/{job_id}/report")
def report(job_id: str, principal=Depends(current), db=Depends(get_db)):
    job = scoped_job(db, principal.user.tenant_id, job_id)
    if not job.report:
        raise HTTPException(409, "Report ešte nie je dostupný.")
    return JSONResponse(content={"job": job_json(job, detail=True), "notice": "Basic inspection only. Not certified PDF/X or print-ready approval."},
                        headers={"Content-Disposition": f'attachment; filename="presspilot-{job.id}.json"'})


@app.get("/api/jobs/{job_id}/original")
def original(job_id: str, principal=Depends(current), db=Depends(get_db)):
    job = scoped_job(db, principal.user.tenant_id, job_id)
    path = job_dir(job.tenant_id, job.id) / "original.pdf"
    if not path.is_file():
        raise HTTPException(404, "Originál nie je dostupný.")
    audit(db, job.tenant_id, "job.original_downloaded", actor_id=principal.user.id, job_id=job.id)
    db.commit()
    return FileResponse(path, media_type="application/pdf", filename=job.filename, content_disposition_type="attachment")


@app.get("/api/jobs/{job_id}/preview")
def preview(job_id: str, principal=Depends(current), db=Depends(get_db)):
    job = scoped_job(db, principal.user.tenant_id, job_id)
    path = job_dir(job.tenant_id, job.id) / "preview.png"
    if not job.preview_available or not path.is_file():
        raise HTTPException(404, "Náhľad nie je dostupný.")
    return FileResponse(path, media_type="image/png")


@app.post("/api/jobs/{job_id}/review")
def review(job_id: str, payload: ReviewIn, principal=Depends(operator), db=Depends(get_db)):
    job = scoped_job(db, principal.user.tenant_id, job_id)
    if not payload.acknowledge_limits:
        raise HTTPException(422, "Potvrďte rozsah a obmedzenia základnej kontroly.")
    if job.status not in ("review", "blocked"):
        raise HTTPException(409, "Táto zákazka sa ešte nedá posúdiť.")
    if payload.decision == "accepted" and job.status != "review":
        raise HTTPException(409, "Zákazku s chybami nie je možné prijať. Vyžiadajte opravený podklad.")
    if not job.report or job.report.get("print_ready") is not False or job.report.get("release_allowed") is not False:
        raise HTTPException(409, "Chýba platný základný report.")
    changed = db.execute(update(Job).where(Job.id == job.id, Job.tenant_id == principal.user.tenant_id,
                    Job.status == job.status, Job.decision.is_(None), Job.report_digest == job.report_digest, Job.deleted_at.is_(None))
        .values(decision=payload.decision, decision_note=payload.note.strip(), reviewer_id=principal.user.id, reviewed_at=now()))
    if not changed.rowcount:
        raise HTTPException(409, "Zákazku už posúdil iný operátor. Obnovte detail.")
    audit(db, job.tenant_id, "job.reviewed", actor_id=principal.user.id, job_id=job.id, decision=payload.decision, report_digest=job.report_digest,
          scope="internal_handoff_only")
    db.commit()
    db.refresh(job)
    return job_json(job, detail=True)


@app.post("/api/jobs/{job_id}/retry")
def retry(job_id: str, principal=Depends(operator), db=Depends(get_db)):
    job = scoped_job(db, principal.user.tenant_id, job_id)
    changed = db.execute(update(Job).where(Job.id == job.id, Job.tenant_id == job.tenant_id, Job.status == "error", Job.attempts < 3)
        .values(status="queued", report=None, report_digest=None, error_code=None, completed_at=None, preview_available=False))
    if not changed.rowcount:
        raise HTTPException(409, "Opakovanie je možné iba pri systémovej chybe a najviac trikrát.")
    audit(db, job.tenant_id, "job.retried", actor_id=principal.user.id, job_id=job.id)
    db.commit()
    db.refresh(job)
    return job_json(job)


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str, principal=Depends(owner), db=Depends(get_db)):
    job = scoped_job(db, principal.user.tenant_id, job_id)
    if job.status == "processing":
        raise HTTPException(409, "Počkajte na dokončenie práve spustenej kontroly.")
    db.rollback()
    if not erase_job(job_id, principal.user.tenant_id, principal.user.id):
        raise HTTPException(503, "Vymazanie súborov sa nedokončilo. Správca ho musí overiť.")
    return {"ok": True}


@app.post("/api/jobs/{job_id}/assistant")
def assistant(job_id: str, principal=Depends(operator), db=Depends(get_db)):
    job = scoped_job(db, principal.user.tenant_id, job_id)
    if not job.report or job.status not in ("review", "blocked"):
        raise HTTPException(409, "Najprv dokončite technickú kontrolu.")
    findings = job.report.get("findings", [])
    meaningful = [f for f in findings if f["severity"] != "info"]
    summary = "\n".join(f"• {f['message']}" + (f" (strana {f['page']})" if f.get("page") else "") for f in meaningful[:12])
    message = ("Dobrý deň, pri technickej kontrole podkladu sme našli tieto body:\n\n" + summary +
               "\n\nProsíme o kontrolu uvedených bodov a prípadné zaslanie opraveného PDF. Ďakujeme.") if meaningful else (
               "Základná technická kontrola v podporovanom rozsahu nezistila problém. Pred odovzdaním do výroby treba overiť vizuálnu spadávku, správu farieb a profesionálny preflight.")
    mode = "rules"
    warning = None
    config = settings()
    if config.llm_base_url and config.llm_model:
        login_rate_limit(db, "assistant:" + principal.user.id)
        # No file, filename, extracted text, font names or customer identifiers leave this process.
        facts = [{"code": f["code"], "severity": f["severity"], "page": f.get("page"), "message": f["message"]} for f in meaningful[:12]]
        try:
            with httpx.Client(timeout=20, trust_env=False, follow_redirects=False) as client:
                result = client.post(config.llm_base_url.rstrip("/") + "/api/chat", json={"model": config.llm_model,
                    "stream": False, "options": {"temperature": 0.1, "num_predict": 450},
                    "messages": [{"role": "system", "content": "Si DTP asistent. Po slovensky priprav stručný návrh správy zákazníkovi iba z dodaných technických nálezov. Nevymýšľaj rozmery, farby ani príčiny. Nikdy nepotvrdzuj pripravenosť na tlač. Nemáš oprávnenie meniť súbor alebo rozhodnutie. Výstup je návrh na kontrolu človekom."},
                                 {"role": "user", "content": __import__("json").dumps(facts, ensure_ascii=False)}]})
                result.raise_for_status()
                content = result.json().get("message", {}).get("content")
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("Empty assistant response")
                message, mode = content[:6000], "ollama"
        except (httpx.HTTPError, ValueError):
            warning = "Lokálny model neodpovedal; zobrazuje sa overiteľná pravidlová šablóna."
    audit(db, job.tenant_id, "job.assistant_generated", actor_id=principal.user.id, job_id=job.id, mode=mode)
    db.commit()
    return {"mode": mode, "text": message, "warning": warning, "requires_human_review": True, "changes_verdict": False}


@app.get("/api/audit")
def events(limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
           job_id: str = Query(default="", max_length=36), principal=Depends(current), db=Depends(get_db)):
    scope = [Audit.tenant_id == principal.user.tenant_id]
    if job_id:
        scope.append(Audit.job_id == job_id)
    records = db.scalars(select(Audit).where(*scope).order_by(Audit.created_at.desc(), Audit.id.desc()).offset(offset).limit(limit)).all()
    return {"items": [{"id": e.id, "action": e.action, "actor_id": e.actor_id, "job_id": e.job_id, "details": e.details, "created_at": e.created_at} for e in records],
            "total": db.scalar(select(func.count()).select_from(Audit).where(*scope)), "offset": offset, "limit": limit}


@app.get("/api/members")
def members(principal=Depends(owner), db=Depends(get_db)):
    return [member_json(u) for u in db.scalars(select(User).where(User.tenant_id == principal.user.tenant_id).order_by(User.created_at)).all()]


@app.post("/api/members", status_code=201)
def add_member(payload: MemberIn, principal=Depends(owner), db=Depends(get_db)):
    if db.scalar(select(func.count()).select_from(User).where(User.tenant_id == principal.user.tenant_id)) >= 30:
        raise HTTPException(409, "Dosiahnutý limit 30 používateľov pilotného pracoviska.")
    user = User(tenant_id=principal.user.tenant_id, email=payload.email, password_hash=hasher.hash(payload.password), role=payload.role)
    db.add(user)
    try:
        db.flush()
        audit(db, user.tenant_id, "member.created", actor_id=principal.user.id, member_id=user.id, role=user.role)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Tento e-mail už má účet v pracovisku.")
    return member_json(user)


@app.delete("/api/members/{member_id}")
def deactivate_member(member_id: str, principal=Depends(owner), db=Depends(get_db)):
    user = db.scalar(select(User).where(User.id == member_id, User.tenant_id == principal.user.tenant_id))
    if not user:
        raise HTTPException(404, "Používateľ sa nenašiel.")
    if user.id == principal.user.id:
        raise HTTPException(409, "Vlastný účet nie je možné deaktivovať touto akciou.")
    user.active = False
    db.execute(delete(SessionToken).where(SessionToken.user_id == user.id))
    db.execute(update(ApiKey).where(ApiKey.user_id == user.id).values(revoked_at=now()))
    audit(db, user.tenant_id, "member.deactivated", actor_id=principal.user.id, member_id=user.id)
    db.commit()
    return {"ok": True}


@app.get("/api/keys")
def keys(principal=Depends(owner), db=Depends(get_db)):
    return [{"id": k.id, "name": k.name, "prefix": k.prefix, "scope": k.scope, "expires_at": k.expires_at, "revoked_at": k.revoked_at}
            for k in db.scalars(select(ApiKey).where(ApiKey.tenant_id == principal.user.tenant_id).order_by(ApiKey.created_at.desc())).all()]


@app.post("/api/keys", status_code=201)
def create_key(payload: KeyIn, principal=Depends(owner), db=Depends(get_db)):
    if db.scalar(select(func.count()).select_from(ApiKey).where(ApiKey.tenant_id == principal.user.tenant_id, ApiKey.revoked_at.is_(None), ApiKey.expires_at > now())) >= 20:
        raise HTTPException(409, "Dosiahnutý limit 20 aktívnych API kľúčov.")
    raw = "pp_" + secrets.token_urlsafe(40)
    key = ApiKey(tenant_id=principal.user.tenant_id, user_id=principal.user.id, name=payload.name, prefix=raw[:12], token_hash=token_hash(raw),
                 scope=payload.scope, expires_at=now()+payload.expires_days*86400)
    db.add(key)
    db.flush()
    audit(db, key.tenant_id, "key.created", actor_id=principal.user.id, key_id=key.id, scope=key.scope)
    db.commit()
    return {"id": key.id, "token": raw, "expires_at": key.expires_at, "notice": "Kľúč sa zobrazí iba raz. Uložte ho do správcu tajomstiev."}


@app.delete("/api/keys/{key_id}")
def revoke_key(key_id: str, principal=Depends(owner), db=Depends(get_db)):
    key = db.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.tenant_id == principal.user.tenant_id))
    if not key:
        raise HTTPException(404, "API kľúč sa nenašiel.")
    key.revoked_at = now()
    audit(db, key.tenant_id, "key.revoked", actor_id=principal.user.id, key_id=key.id)
    db.commit()
    return {"ok": True}


@app.get("/api/openapi.json")
def openapi(principal=Depends(current)):
    return app.openapi()


@app.get("/")
def index():
    path = settings().static_dir.resolve() / "index.html"
    if not path.is_file():
        return JSONResponse(status_code=503, content={"detail": "Frontend nie je zostavený. Spustite npm run build v adresári frontend."})
    return FileResponse(path, headers={"Cache-Control": "no-store"})


app.mount("/assets", StaticFiles(directory=str(settings().static_dir.resolve() / "assets"), check_dir=False), name="assets")
