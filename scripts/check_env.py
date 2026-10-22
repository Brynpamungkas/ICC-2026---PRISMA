"""Catat OS, versi alat, GPU, VRAM, vLLM/Ollama dan digest model ke docs/env/<hostname>.json (E1/E3/E8).

Hanya MEMBACA keadaan mesin; tidak memasang apa pun. Komponen yang tidak ditemukan dicatat
sebagai null (bukan error) agar mesin CPU-only tetap bisa dicatat. Hasil adalah bukti mesin
tempat skrip dijalankan, bukan klaim G-ENV lulus.
  python scripts/check_env.py [--model-dir PATH_SNAPSHOT_HF]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as md
import json
import platform
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY_PACKAGES = ["vllm", "torch", "transformers", "pydantic", "sqlglot", "pandas", "pyyaml", "requests", "fastapi", "pytest"]


def run(cmd: list[str], timeout: int = 20) -> str | None:
    if shutil.which(cmd[0]) is None:
        return None
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (out.stdout or out.stderr).strip() or None


def pkg_version(name: str) -> str | None:
    try:
        return md.version(name)
    except md.PackageNotFoundError:
        return None


def gpu_info() -> dict:
    q = run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used,memory.free", "--format=csv,noheader,nounits"])
    gpus = []
    for line in (q or "").splitlines():
        name, driver, total, used, free = [x.strip() for x in line.split(",")]
        gpus.append({"name": name, "driver": driver, "vram_total_mib": int(total), "vram_used_mib": int(used), "vram_free_mib": int(free)})
    return {"nvidia_smi_found": q is not None, "gpus": gpus}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def model_digests(model_dir: Path | None) -> dict | None:
    if model_dir is None:
        return None
    files = sorted(p for p in model_dir.rglob("*") if p.is_file() and p.suffix in {".safetensors", ".bin", ".gguf", ".json", ".txt"})
    return {str(p.relative_to(model_dir)): sha256_file(p) for p in files}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-dir", type=Path, help="folder snapshot model (mis. ~/.cache/huggingface/hub/models--Qwen--.../snapshots/<rev>)")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    host = socket.gethostname()
    info = {
        "recorded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hostname": host,
        "os": platform.platform(),
        "wsl": "microsoft" in platform.release().lower(),
        "python": sys.version.split()[0],
        "tools": {t: run([t, "--version"]) for t in ["git", "make", "node", "npm", "docker", "ollama", "llama-server"]},
        "packages": {p: pkg_version(p) for p in PY_PACKAGES},
        "sqlite3_python_lib": __import__("sqlite3").sqlite_version,
        "gpu": gpu_info(),
        "model_files_sha256": model_digests(a.model_dir),
        "notes": "Bukti statis mesin ini. Python target proyek = 3.11; CUDA 'Version' di nvidia-smi bukan bukti toolkit.",
    }
    out = a.out or (ROOT / "docs" / "env" / f"{host}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: info[k] for k in ("hostname", "os", "wsl", "python")}, indent=2))
    print("GPU:", info["gpu"]["gpus"] or "tidak terdeteksi (nvidia-smi tidak ada/tidak berjalan)")
    print("vLLM:", info["packages"]["vllm"] or "belum terpasang")
    if info["python"].split(".")[:2] != ["3", "11"]:
        print(f"PERHATIAN: Python {info['python']} (proyek menargetkan 3.11).")
    print(f"Ditulis: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
