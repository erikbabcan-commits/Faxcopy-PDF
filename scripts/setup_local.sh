#!/bin/bash
# Compatible with the Bash 3.2 shipped with macOS. No sudo or global pip installs.
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077

mode="${1:-setup}"
case "$mode" in
  setup|--verify) ;;
  *) echo 'Usage: bash scripts/setup_local.sh [--verify]' >&2; exit 2 ;;
esac

if [ -x .venv/bin/python ]; then
  python_bin=.venv/bin/python
else
  python_bin=''
  for candidate in python3.13 python3.12 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; sys.exit(not ((3, 12) <= sys.version_info[:2] <= (3, 13)))'; then
      python_bin="$candidate"
      break
    fi
  done
  if [ -z "$python_bin" ]; then
    echo 'Install Python 3.13 (macOS universal2 installer) from https://www.python.org/downloads/macos/' >&2
    echo 'Then reopen Terminal and rerun this command. The system Python is not modified.' >&2
    exit 1
  fi
  if [ -e .venv ]; then
    echo '.venv exists but has no usable Python. Move it aside manually before retrying.' >&2
    exit 1
  fi
  "$python_bin" -m venv .venv
  python_bin=.venv/bin/python
fi
"$python_bin" -c 'import sys; sys.exit(0 if (3, 12) <= sys.version_info[:2] <= (3, 13) else "Use Python 3.12 or 3.13; move the incompatible .venv aside first.")'
"$python_bin" -m pip install --only-binary=:all: -r backend/requirements.txt
"$python_bin" -m pip check
"$python_bin" -c 'import pypdfium2; from PIL import Image; import sqlalchemy, argon2, uvicorn; print("Runtime imports OK")'
test -f frontend/dist/index.html || { echo 'Missing frontend build. See docs/MACBOOK_AIR.md.' >&2; exit 1; }

if [ "$mode" = --verify ]; then
  "$python_bin" -m pip install --only-binary=:all: pytest==9.0.2
  (cd backend && ../.venv/bin/python -m pytest -q)
  "$python_bin" scripts/http_smoke.py --report .local/verification/http-results.json
  echo 'Verification passed. Disposable test data was removed; your workspace was not changed.'
  exit 0
fi

if ! "$python_bin" - <<'PY'
from pathlib import Path
import sqlite3
import sys
path = Path('.local/presspilot.db').resolve()
if not path.exists():
    sys.exit(1)
try:
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        exists = db.execute("SELECT 1 FROM users WHERE role='owner' AND active=1 LIMIT 1").fetchone()
    sys.exit(0 if exists else 1)
except sqlite3.Error:
    sys.exit(1)
PY
then
  read -r -p 'Workspace name [VORKEI]: ' workspace
  read -r -p 'Login email: ' email
  "$python_bin" scripts/run_local.py init --workspace "${workspace:-VORKEI}" --email "$email" --seed-demo
else
  echo 'Existing local database preserved. Login details: .local/workspace.json (if created by this launcher).'
fi
echo 'Start: bash Start-PressPilot.command'
echo 'Then open http://localhost:8080. Stop both services with Ctrl+C.'
