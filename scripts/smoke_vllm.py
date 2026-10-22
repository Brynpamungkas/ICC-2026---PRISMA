"""Uji E4/E5: permintaan n sampel ke penyaji vLLM. Mencetak waktu, token, VRAM, dan menyimpan ringkasan JSON.

Jalankan setelah `make serve` aktif (terminal Ubuntu lain):
  make smoke                     # n=64
  python scripts/smoke_vllm.py 1 8 16 32 64   # beberapa nilai n berurutan (E5 / ablasi kasar)
URL, model, dan decoding dibaca dari config/config.yaml. Prompt skema di bawah adalah SYNTHETIC
(pengulangan teks), BUKAN bukti jumlah token nyata ~1.500 (lihat D12 ENV-E5-01): jumlah token
yang dilaporkan server dicatat apa adanya. Hasil satu run bukan p50/p95.
"""
import json
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load(open(ROOT / "config" / "config.yaml", encoding="utf-8"))
URL = CFG["model"]["url"]
MODEL = CFG["model"]["name"]
S = CFG["sampling"]
NS = [int(x) for x in sys.argv[1:]] or [S["n_samples"]]

schema = ("Tabel provinsi(kode, nama); indikator(kode, nama_kanonik, satuan); "
          "nilai_indikator(kode_provinsi, kode_indikator, periode, nilai). ") * 20
PROMPT = schema + " Tulis satu SELECT untuk provinsi dengan nilai tertinggi pada :indikator."


def vram_used_mib():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
        return int(out[0]) if out else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


results = []
for n in NS:
    payload = {"model": MODEL, "messages": [{"role": "user", "content": PROMPT}], "n": n,
               "max_tokens": S["max_output_tokens"], "temperature": S["temperature"],
               "top_p": S["top_p"], "seed": S["seed"]}
    before = vram_used_mib()
    t0 = time.monotonic()
    try:
        r = requests.post(URL, json=payload, timeout=600)
        dt = time.monotonic() - t0
        r.raise_for_status()
    except requests.RequestException as exc:
        print(f"GAGAL n={n}: {exc}. Server sudah jalan? (make serve)")
        results.append({"n_diminta": n, "error": str(exc)})
        continue
    data = r.json()
    choices = data["choices"]
    after = vram_used_mib()
    rec = {"n_diminta": n, "n_diterima": len(choices), "detik": round(dt, 2),
           "prompt_tokens": data["usage"]["prompt_tokens"], "completion_tokens": data["usage"]["completion_tokens"],
           "finish_reasons": sorted({c.get("finish_reason") for c in choices}, key=str),
           "vram_used_mib_sebelum": before, "vram_used_mib_sesudah": after}
    results.append(rec)
    print(json.dumps(rec, indent=2))
    if n == NS[-1]:
        print("--- contoh keluaran ---")
        print(choices[0]["message"]["content"])

out = ROOT / "docs" / "env" / f"smoke_{socket.gethostname()}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"recorded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                           "model": MODEL, "synthetic_prompt": True, "results": results}, indent=2) + "\n", encoding="utf-8")
print(f"Ringkasan: {out}")
sys.exit(1 if any("error" in x for x in results) else 0)
