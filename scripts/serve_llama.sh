#!/usr/bin/env bash
# Explicit CPU fallback from D12. No model is downloaded at service startup.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${PRISMA_PYTHON:-$ROOT/.venv/bin/python}"
exec "$PY" - <<'PY'
import os
from backend.app.config import ROOT, load_config
from scripts.setup_local import verify_hash

cfg = load_config()
if cfg["model"]["backend"] != "llama_cpp":
    raise SystemExit("Pilih profil CPU secara eksplisit: PRISMA_CONFIG=config/local.cpu.yaml")
settings = cfg["llama_cpp"]
if settings["gpu_layers"] != 0:
    raise SystemExit("Launcher ini khusus CPU; offload GPU memerlukan profil terpisah.")
samples = cfg["sampling"]["n_samples"]
if isinstance(samples, bool) or not isinstance(samples, int) or samples <= 0:
    raise SystemExit("Jumlah sampel harus bilangan bulat positif.")
binary = ROOT / settings["binary"]
model = ROOT / settings["model_file"]
if not binary.is_file() or not model.is_file():
    raise SystemExit("llama-server/bobot belum tersedia. Jalankan bash scripts/setup_local.sh --cpu.")
try:
    digest = verify_hash(model, settings["expected_sha256"])
except ValueError as exc:
    raise SystemExit(str(exc)) from exc
if cfg["model"]["digest"] != digest:
    raise SystemExit("Profil dan hash bobot berbeda; profil tidak diganti otomatis.")
print("CPU/GGUF fallback; hasil terpisah dari baseline vLLM/AWQ/N=64.", flush=True)
args = [str(binary), "--model", str(model), "--alias", cfg["model"]["name"],
        "--n-gpu-layers", str(settings["gpu_layers"]), "--parallel", str(samples), "--host", settings["host"],
        "--port", str(settings["port"])]
print("Startup arguments:", args, flush=True)
os.execv(binary, args)
PY
