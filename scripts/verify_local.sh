#!/usr/bin/env bash
# Explicit CPU-only verification; no installs or changes to research labels/config.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PRISMA_CONFIG="${PRISMA_CONFIG:-config/local.cpu.yaml}"
PY="${PRISMA_PYTHON:-.venv/bin/python}"
exec "$PY" -B -m scripts.verify_local "$@"
