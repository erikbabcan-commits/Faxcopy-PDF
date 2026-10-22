from pathlib import Path
import re
import uuid
from .config import settings


def job_dir(tenant_id: str, job_id: str) -> Path:
    # Filesystem keys never contain customer-supplied filenames.
    tenant, job = str(uuid.UUID(tenant_id)), str(uuid.UUID(job_id))
    return settings().data_dir.resolve() / "documents" / tenant / job


def safe_name(filename: str) -> str:
    name = filename.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip(" .")
    return (name or "document.pdf")[:180]
