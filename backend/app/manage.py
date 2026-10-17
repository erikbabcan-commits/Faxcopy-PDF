"""Operator-only provisioning. No public registration or default passwords."""
import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import shutil
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, select
from .config import settings
from .db import audit, session_factory
from .models import ApiKey, Job, Profile, SessionToken, Tenant, User, now, uid
from .schemas import PRESETS, MemberIn, digest
from .security import hasher
from .storage import job_dir


def provision(db, name: str, email: str, password: str):
    user_data = MemberIn(email=email, password=password, role="owner")
    if not 2 <= len(name.strip()) <= 120:
        raise ValueError("Workspace name must be 2–120 characters")
    tenant = Tenant(name=name.strip())
    db.add(tenant)
    db.flush()
    user = User(tenant_id=tenant.id, email=user_data.email, password_hash=hasher.hash(password), role="owner")
    db.add(user)
    db.flush()
    for label, rules in PRESETS:
        db.add(Profile(tenant_id=tenant.id, name=label, rules=rules, digest=digest(rules)))
    audit(db, tenant.id, "workspace.created", actor_id=user.id)
    db.commit()
    return tenant, user


def migrate():
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(config, "head")


def seed_demo(workspace_id: str, samples: Path):
    with session_factory()() as db:
        tenant = db.get(Tenant, workspace_id)
        if not tenant:
            raise ValueError("Unknown workspace")
        owner = db.scalar(select(User).where(User.tenant_id == workspace_id, User.role == "owner", User.active.is_(True)))
        profile = db.scalar(select(Profile).where(Profile.tenant_id == workspace_id, Profile.name.like("Vizitka%")))
        if not owner or not profile:
            raise ValueError("Bootstrap a workspace with default profiles first")
        for index, source in enumerate(sorted(samples.glob("*.pdf")), 1):
            if index > 8:
                break
            key = f"demo-fixture-{source.stem}"
            if db.scalar(select(Job).where(Job.tenant_id == workspace_id, Job.idempotency_key == key)):
                continue
            job_id = uid()
            target = job_dir(workspace_id, job_id)
            target.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target / "original.pdf")
            (target / "original.pdf").chmod(0o440)
            data = source.read_bytes()
            job = Job(id=job_id, tenant_id=workspace_id, creator_id=owner.id, idempotency_key=key, order_ref=f"DEMO-{1000+index}",
                      filename=source.name, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), profile_id=profile.id,
                      profile_snapshot=profile.rules, profile_digest=profile.digest, profile_name=profile.name, profile_version=profile.version)
            db.add(job)
            tenant.quota_month = datetime.now(timezone.utc).strftime("%Y-%m")
            tenant.monthly_uploads += 1
            tenant.storage_bytes += len(data)
            audit(db, workspace_id, "job.demo_uploaded", actor_id=owner.id, job_id=job_id)
        db.commit()
    print("Synthetic demo PDFs queued. Run the worker to produce real inspection reports.")


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate")
    boot = commands.add_parser("bootstrap")
    boot.add_argument("--email", required=True)
    boot.add_argument("--workspace", required=True)
    reset = commands.add_parser("reset-password")
    reset.add_argument("--workspace-id", required=True)
    reset.add_argument("--email", required=True)
    demo = commands.add_parser("seed-demo")
    demo.add_argument("--workspace-id", required=True)
    demo.add_argument("--samples", type=Path, default=Path("../samples"))
    demo.add_argument("--confirm-synthetic-data", action="store_true", required=True)
    commands.add_parser("purge-expired")
    commands.add_parser("work-once")
    args = parser.parse_args()
    if args.command == "migrate":
        migrate()
    elif args.command == "bootstrap":
        password = os.getenv("PP_BOOTSTRAP_PASSWORD") or getpass.getpass("Owner password (at least 12 characters): ")
        if not os.getenv("PP_BOOTSTRAP_PASSWORD") and password != getpass.getpass("Repeat password: "):
            parser.error("Passwords do not match")
        with session_factory()() as db:
            tenant, user = provision(db, args.workspace, args.email, password)
            print(json.dumps({"workspace_id": tenant.id, "workspace": tenant.name, "email": user.email}, indent=2))
    elif args.command == "reset-password":
        password = getpass.getpass("New password (at least 12 characters): ")
        MemberIn(email=args.email, password=password)
        if password != getpass.getpass("Repeat password: "):
            parser.error("Passwords do not match")
        with session_factory()() as db:
            user = db.scalar(select(User).where(User.tenant_id == args.workspace_id, User.email == args.email.lower().strip()))
            if not user:
                parser.error("User not found")
            user.password_hash = hasher.hash(password)
            db.execute(delete(SessionToken).where(SessionToken.user_id == user.id))
            for key in db.scalars(select(ApiKey).where(ApiKey.user_id == user.id)).all():
                key.revoked_at = now()
            audit(db, user.tenant_id, "auth.password_reset_by_admin", actor_id=user.id)
            db.commit()
        print("Password reset; sessions and API keys revoked.")
    elif args.command == "seed-demo":
        seed_demo(args.workspace_id, args.samples)
    elif args.command == "purge-expired":
        from .maintenance import purge_due
        print({"purged": purge_due()})
    elif args.command == "work-once":
        from .worker import process_one
        print({"processed": process_one()})


if __name__ == "__main__":
    main()
