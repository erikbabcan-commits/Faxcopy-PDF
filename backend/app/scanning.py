import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import httpx
from .config import settings


class ScanFailure(Exception):
    pass


def local_scan(source: Path, rules: dict, timeout: int = 45) -> dict:
    """Local trusted-demo fallback. Containers add the actual filesystem/network boundary."""
    with tempfile.TemporaryDirectory(prefix="pp-scan-") as tmp:
        root = Path(tmp)
        profile = root / "profile.json"
        profile.write_text(json.dumps(rules), encoding="utf-8")
        environment = {"PATH": os.defpath, "PYTHONUTF8": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
                       "HOME": tmp, "TMPDIR": tmp, "LANG": "C.UTF-8"}
        try:
            with (root / "result.json").open("wb") as output, (root / "stderr.txt").open("wb") as errors:
                process = subprocess.run([sys.executable, "-m", "app.scan_process", str(source.resolve()), str(profile)],
                    cwd=tmp, env=environment, stdout=output, stderr=errors, stdin=subprocess.DEVNULL,
                    timeout=timeout, check=False)
            if process.returncode != 0:
                raise ScanFailure("SCANNER_PROCESS_FAILED")
            if (root / "result.json").stat().st_size > 10 * 1024**2:
                raise ScanFailure("SCANNER_RESPONSE_TOO_LARGE")
            payload = json.loads((root / "result.json").read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or not isinstance(payload.get("report"), dict):
                raise ScanFailure("SCANNER_INVALID_RESPONSE")
            return payload
        except subprocess.TimeoutExpired as exc:
            raise ScanFailure("SCANNER_TIMEOUT") from exc
        except (OSError, ValueError) as exc:
            raise ScanFailure("SCANNER_INVALID_RESPONSE") from exc


def scan(source: Path, rules: dict) -> dict:
    config = settings()
    if not config.scanner_url:
        if config.app_env == "production":
            raise ScanFailure("ISOLATED_SCANNER_REQUIRED")
        return local_scan(source, rules, config.scan_timeout_seconds)
    try:
        with source.open("rb") as pdf, httpx.Client(timeout=config.scan_timeout_seconds + 10, trust_env=False) as client:
            with client.stream("POST", config.scanner_url.rstrip("/") + "/scan",
                    headers={"X-Scanner-Token": config.scanner_token},
                    files={"file": ("input.pdf", pdf, "application/pdf")}, data={"rules": json.dumps(rules)}) as response:
                response.raise_for_status()
                chunks = []
                length = 0
                for chunk in response.iter_bytes():
                    length += len(chunk)
                    if length > 10 * 1024**2:
                        raise ScanFailure("SCANNER_RESPONSE_TOO_LARGE")
                    chunks.append(chunk)
                payload = json.loads(b"".join(chunks))
                if not isinstance(payload, dict) or not isinstance(payload.get("report"), dict):
                    raise ScanFailure("SCANNER_INVALID_RESPONSE")
                return payload
    except httpx.TimeoutException as exc:
        raise ScanFailure("SCANNER_TIMEOUT") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise ScanFailure("SCANNER_UNAVAILABLE") from exc
