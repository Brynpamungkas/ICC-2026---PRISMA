#!/usr/bin/env bash
# Explicit NVIDIA baseline; no automatic fallback or hidden parameter overrides.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${PRISMA_PYTHON:-$ROOT/.venv/bin/python}"
exec "$PY" - <<'PY'
import os
from pathlib import Path
import shutil
import subprocess
import sys
from backend.app.config import load_config

cfg = load_config()
if cfg["model"]["backend"] != "vllm":
    raise SystemExit("Pilih profil vLLM secara eksplisit; backend tidak diganti otomatis.")
if not shutil.which("nvidia-smi"):
    raise SystemExit("NVIDIA belum terverifikasi pada mesin ini; gunakan jalur CPU terpisah.")
subprocess.run(["nvidia-smi"], check=True)
search = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
binary = shutil.which("vllm", path=search)
if not binary:
    raise SystemExit("vLLM belum terpasang pada environment model yang dipilih.")
settings = cfg["vllm"]
args = [binary, "serve", cfg["model"]["name"], "--quantization", settings["quantization"],
        "--dtype", settings["dtype"], "--max-model-len", str(settings["max_model_len"]),
        "--gpu-memory-utilization", str(settings["gpu_memory_utilization"]),
        "--max-num-seqs", str(cfg["sampling"]["n_samples"]), "--port", str(settings["port"])]
if settings["enforce_eager"]:
    args.append("--enforce-eager")
print("Candidate startup arguments:", args, flush=True)
os.execv(binary, args)
PY
