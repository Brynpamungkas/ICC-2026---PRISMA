#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
exec "${PRISMA_PYTHON:-$ROOT/.venv/bin/python}" -B tools/release_cli.py run "$@"
