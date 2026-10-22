#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PY="${PRISMA_PYTHON:-$ROOT/.venv/bin/python}"
export PRISMA_CONFIG="$ROOT/config/config.yaml"
export PYTHONDONTWRITEBYTECODE=1
"$PY" tools/release_cli.py verify
"$PY" -m pytest backend/tests release/tests -q -p no:cacheprovider
"$PY" -m ruff check backend scripts tools/release_cli.py --no-cache
NODE="$ROOT/.local/node-v24.11.0-linux-x64/bin"
if [[ -d "$NODE" ]]; then export PATH="$NODE:$PATH"; fi
cd frontend
npm test
npm run typecheck
npm run build
