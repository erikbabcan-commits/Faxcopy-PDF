from functools import lru_cache
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .config import settings
from .models import Audit


@lru_cache
def engine():
    url = settings().database_url
    args = {"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
    eng = create_engine(url, pool_pre_ping=True, connect_args=args)
    if url.startswith("sqlite"):
        @event.listens_for(eng, "connect")
        def configure_sqlite(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=30000")
    return eng


def session_factory():
    return sessionmaker(engine(), expire_on_commit=False)


def get_db():
    with session_factory()() as db:
        yield db


def audit(db, tenant_id: str, action: str, actor_id=None, job_id=None, **details):
    db.add(Audit(tenant_id=tenant_id, action=action, actor_id=actor_id, job_id=job_id, details=details))
