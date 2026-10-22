#!/usr/bin/env bash
# Jalankan di WSL2/Linux dengan venv aktif. Nilai bawaan dibaca dari config/config.yaml;
# bisa ditimpa lewat variabel lingkungan:  GPU_UTIL=0.7 MAX_LEN=2048 make serve
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cfg() { python - "$ROOT" "$1" << 'PY'
import sys, yaml
root, key = sys.argv[1], sys.argv[2]
c = yaml.safe_load(open(f"{root}/config/config.yaml", encoding="utf-8"))
print({"model": c["model"]["name"], "max_len": c["vllm"]["max_model_len"],
       "gpu_util": c["vllm"]["gpu_memory_utilization"], "port": c["vllm"]["port"]}[key])
PY
}
MODEL="${MODEL:-$(cfg model)}"
MAX_LEN="${MAX_LEN:-$(cfg max_len)}"
GPU_UTIL="${GPU_UTIL:-$(cfg gpu_util)}"
PORT="${PORT:-$(cfg port)}"
MAX_SEQS="${MAX_SEQS:-64}"        # n=64 sampel per permintaan; turunkan bila OOM
echo "[serve_vllm] model=$MODEL max_len=$MAX_LEN gpu_util=$GPU_UTIL port=$PORT max_seqs=$MAX_SEQS"
# --dtype half: AWQ berjalan di fp16. --enforce-eager: hemat VRAM (tanpa CUDA graph). Prefix caching
# bawaan vLLM V1 dipakai agar 64 sampel berbagi prompt (paper Tabel A-2); tambahkan --enable-prefix-caching
# secara manual hanya bila versi vLLM terpasang masih V0 (cek `vllm serve --help`).
exec vllm serve "$MODEL" \
  --quantization awq \
  --dtype half \
  --max-model-len "$MAX_LEN" \
  --gpu-memory-utilization "$GPU_UTIL" \
  --max-num-seqs "$MAX_SEQS" \
  --enforce-eager \
  --port "$PORT"
