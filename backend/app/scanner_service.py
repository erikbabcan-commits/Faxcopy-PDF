"""Private scanner service: no DB, document volume, customer identities or cloud keys."""
import json
import os
from pathlib import Path
import secrets
import tempfile
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from .schemas import Rules
from .scanning import local_scan, ScanFailure

app = FastAPI(title="PressPilot isolated scanner", docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/healthz")
def health():
    return {"status": "ok"}


@app.post("/scan")
def run_scan(file: UploadFile = File(...), rules: str = Form(...), x_scanner_token: str = Header(default="")):
    expected = os.getenv("SCANNER_TOKEN", "")
    if len(expected) < 32 or not secrets.compare_digest(expected, x_scanner_token):
        raise HTTPException(401, "Unauthorized")
    if len(rules) > 8192:
        raise HTTPException(413, "Profile too large")
    try:
        profile = Rules.model_validate(json.loads(rules)).model_dump()
    except ValueError:
        raise HTTPException(422, "Invalid profile")
    max_bytes = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024**2
    with tempfile.TemporaryDirectory(prefix="pp-input-") as tmp:
        path = Path(tmp) / "input.pdf"
        size = 0
        with path.open("wb") as output:
            while chunk := file.file.read(1024**2):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(413, "File too large")
                output.write(chunk)
        try:
            return local_scan(path, profile, int(os.getenv("SCAN_TIMEOUT_SECONDS", "45")))
        except ScanFailure as exc:
            raise HTTPException(422, str(exc))

from .middleware import BodyLimitMiddleware
app.add_middleware(BodyLimitMiddleware, max_bytes=int(os.getenv("MAX_UPLOAD_MB", "25"))*1024**2+256*1024)
