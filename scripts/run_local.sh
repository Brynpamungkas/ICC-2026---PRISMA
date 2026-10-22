#!/usr/bin/env bash
# Foreground three-process launcher; only children started here are stopped.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PROFILE="${1:-baseline}"
if [[ $# -gt 1 || ( "$PROFILE" != cpu && "$PROFILE" != baseline ) ]]; then
  echo "Pemakaian: bash scripts/run_local.sh [cpu|baseline]" >&2; exit 2
fi
export PRISMA_PYTHON="${PRISMA_PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PRISMA_PYTHON" ]]; then echo "Jalankan bash scripts/setup_local.sh --cpu dahulu." >&2; exit 1; fi
if [[ "$PROFILE" == cpu ]]; then
  export PRISMA_CONFIG="$ROOT/config/local.cpu.yaml"
  MODEL_SCRIPT=scripts/serve_llama.sh
else
  export PRISMA_CONFIG="$ROOT/config/config.yaml"
  MODEL_SCRIPT=scripts/serve_vllm.sh
fi
if [[ ! -f "$PRISMA_CONFIG" ]]; then echo "Profil belum tersedia; jalankan setup lokal." >&2; exit 1; fi
"$PRISMA_PYTHON" -c 'import fastapi, uvicorn, sqlglot, pandas, pydantic, requests, yaml' || {
  echo "Dependensi belum lengkap; jalankan setup lokal." >&2; exit 1;
}
if [[ ! -f data/prisma.sqlite ]]; then echo "Database belum tersedia; jalankan setup lokal." >&2; exit 1; fi
if [[ ! -f frontend/.next/BUILD_ID ]]; then echo "Build frontend belum tersedia; jalankan setup lokal." >&2; exit 1; fi
NODE_VERSION="$("$PRISMA_PYTHON" -c 'from backend.app.config import load_config;print(load_config()["local_setup"]["node_version"])')"
if [[ -x "$ROOT/.local/node-v$NODE_VERSION-linux-x64/bin/node" ]]; then
  export PATH="$ROOT/.local/node-v$NODE_VERSION-linux-x64/bin:$PATH"
elif [[ -x "$ROOT/.local/node-v$NODE_VERSION-linux-arm64/bin/node" ]]; then
  export PATH="$ROOT/.local/node-v$NODE_VERSION-linux-arm64/bin:$PATH"
fi
command -v node >/dev/null || { echo "Node belum terpasang." >&2; exit 1; }
PIDS=()
cleanup() {
  trap - EXIT INT TERM
  for pid in "${PIDS[@]}"; do kill -TERM "$pid" 2>/dev/null || true; done
  for pid in "${PIDS[@]}"; do wait "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT
trap 'exit 130' INT TERM
bash "$MODEL_SCRIPT" & PIDS+=("$!")
"$PRISMA_PYTHON" -m backend.app.main & PIDS+=("$!")
node frontend/scripts/run.mjs start & PIDS+=("$!")
"$PRISMA_PYTHON" -c 'from backend.app.config import load_config;c=load_config();print("Buka http://%s:%s; tunggu model siap, lalu Periksa lagi."%(c["frontend"]["host"],c["frontend"]["port"]))'
echo "Ctrl+C menghentikan proses sesi ini. Pengujian nyata G3/G4 tetap memerlukan bukti."
wait -n "${PIDS[@]}"
