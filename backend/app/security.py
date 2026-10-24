import hashlib
import secrets
import time
from dataclasses import dataclass
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from .config import settings
from .db import get_db
from .models import ApiKey, LoginBucket, SessionToken, User

hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
DUMMY_HASH = hasher.hash("constant-work-factor-unmatched-account")
COOKIE = "pp_session"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def check_origin(request: Request):
    # Browsers must supply an exact Origin for writes. CLI clients use the same header.
    if request.headers.get("origin") != settings().app_origin:
        raise HTTPException(403, "Požiadavka nepochádza z povoleného pôvodu.")


def login_rate_limit(db, raw_key: str):
    stamp = int(time.time())
    key = token_hash(raw_key)
    insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
    db.execute(insert(LoginBucket).values(key=key, attempts=0, reset_at=stamp + 900)
               .on_conflict_do_nothing(index_elements=["key"]))
    db.execute(update(LoginBucket).where(LoginBucket.key == key, LoginBucket.reset_at <= stamp)
               .values(attempts=0, reset_at=stamp + 900))
    attempts = db.execute(update(LoginBucket).where(LoginBucket.key == key)
                         .values(attempts=LoginBucket.attempts + 1)
                         .returning(LoginBucket.attempts)).scalar_one()
    db.commit()  # Failed attempts must survive later authentication failures.
    if attempts > 12:
        raise HTTPException(429, "Príliš veľa pokusov. Skúste to o 15 minút.", headers={"Retry-After": "900"})


@dataclass
class Principal:
    user: User
    session: SessionToken | None


def current(request: Request, db=Depends(get_db)) -> Principal:
    authorization = request.headers.get("authorization", "")
    if authorization:
        if not authorization.startswith("Bearer pp_") or len(authorization) > 160:
            raise HTTPException(401, "Neplatný API kľúč.")
        key = db.scalar(select(ApiKey).where(ApiKey.token_hash == token_hash(authorization[7:])))
        if not key or key.revoked_at or key.expires_at <= int(time.time()):
            raise HTTPException(401, "Neplatný alebo expirovaný API kľúč.")
        user = db.get(User, key.user_id)
        if not user or not user.active or user.tenant_id != key.tenant_id:
            raise HTTPException(401, "Účet API kľúča nie je aktívny.")
        path = request.url.path
        readable = request.method == "GET" and (path == "/api/profiles" or path == "/api/jobs" or path.startswith("/api/jobs/"))
        uploadable = request.method == "POST" and path == "/api/jobs" and key.scope == "upload"
        if not (readable or uploadable):
            raise HTTPException(403, "API kľúč nemá oprávnenie na túto akciu.")
        return Principal(user, None)
    token = request.cookies.get(COOKIE, "")
    if len(token) < 32 or len(token) > 128:
        raise HTTPException(401, "Prihláste sa.")
    session = db.get(SessionToken, token_hash(token))
    if not session or session.expires_at <= int(time.time()):
        raise HTTPException(401, "Relácia vypršala. Prihláste sa znova.")
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise HTTPException(401, "Účet nie je aktívny.")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        check_origin(request)
        if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), session.csrf_token):
            raise HTTPException(403, "Neplatný CSRF token. Obnovte stránku.")
    return Principal(user, session)


def operator(principal=Depends(current)):
    if principal.user.role not in ("owner", "operator"):
        raise HTTPException(403, "Táto akcia vyžaduje rolu operátora.")
    return principal


def owner(principal=Depends(current)):
    if principal.user.role != "owner":
        raise HTTPException(403, "Táto akcia vyžaduje vlastníka pracoviska.")
    return principal


def new_session(db, user: User):
    raw = secrets.token_urlsafe(48)
    session = SessionToken(token_hash=token_hash(raw), user_id=user.id,
                           csrf_token=secrets.token_urlsafe(32),
                           expires_at=int(time.time()) + settings().session_ttl_seconds)
    db.execute(delete(SessionToken).where(SessionToken.expires_at < int(time.time())))
    db.add(session)
    return raw, session
