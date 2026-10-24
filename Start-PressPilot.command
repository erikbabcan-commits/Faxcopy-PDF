#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo 'First run: bash scripts/setup_local.sh' >&2
  exit 1
fi
exec .venv/bin/python scripts/run_local.py serve
