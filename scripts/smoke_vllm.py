"""SYNTHETIC transport smoke; keep raw HTTP evidence from every run.

Usage: python -m scripts.smoke_vllm [1 8 16 32 64] [--out NEW_DIRECTORY]
This is not accuracy evaluation, p50/p95, or automatic G3 acceptance.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.config import load_config  # noqa: E402
from backend.app.llm.client import LlmClient, LlmUnavailable  # noqa: E402

PROMPT = ("SYNTHETIC fixture: SQLite table sample(indicator_code TEXT, value REAL). "
          "Write one SELECT returning MAX(value) AS nilai with indicator_code=:indikator. "
          "Return SQL only. No real statistics are involved.")


def vram_used_mib() -> list[int] | None:
    """Device readings, explicitly not a measurement of peak allocated VRAM."""
    try:
        result = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, timeout=10, check=True)
        return [int(line) for line in result.stdout.splitlines()]
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def run_smoke(config: dict, counts: list[int], output: Path, *, client_factory=LlmClient) -> bool:
    if not counts or any(isinstance(n, bool) or not isinstance(n, int) or n <= 0 for n in counts):
        raise ValueError("Jumlah sampel harus bilangan bulat positif.")
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    cfg = deepcopy(config)
    cfg["transport"]["trace_dir"] = str(output.resolve() / "transport")
    results = []
    for n in counts:
        client = client_factory(cfg)
        row = {"requested_n": n, "received_n": 0, "passed_transport": False,
               "vram_before_mib": vram_used_mib(), "trace_path": None}
        started = time.monotonic()
        try:
            values = client.generate(PROMPT, n)
            row["received_n"] = len(values)
            trace = json.loads(client.last_trace_path.read_text(encoding="utf-8"))
            choices = (trace.get("response") or {}).get("choices", [])
            row["finish_reasons"] = [choice.get("finish_reason") for choice in choices]
            row["usage"] = (trace.get("response") or {}).get("usage")
            tokens = (row["usage"] or {}).get("completion_tokens")
            duration = trace.get("duration_s")
            row["completion_tokens_per_second_http"] = (tokens / duration if isinstance(tokens, int)
                and isinstance(duration, (int, float)) and duration > 0 else None)
            row["passed_transport"] = (len(values) == n and all(value.strip() for value in values)
                                       and len(choices) == n
                                       and all(choice.get("finish_reason") == "stop" for choice in choices))
        except LlmUnavailable as exc:
            row["error_category"] = type(exc).__name__
        finally:
            row["duration_s"] = time.monotonic() - started
            row["vram_after_mib"] = vram_used_mib()
            row["trace_path"] = str(client.last_trace_path) if client.last_trace_path else None
            results.append(row)
    software = {}
    for package in ["requests", "vllm", "torch", "pydantic"]:
        try:
            software[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            software[package] = None
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                            text=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout)
    resolved = json.dumps(cfg, sort_keys=True, ensure_ascii=False).encode()
    report = {"run_id": output.name, "recorded_at": datetime.now(timezone.utc).isoformat(),
              "purpose": "SYNTHETIC_TRANSPORT_SMOKE", "synthetic_prompt": True,
              "backend": cfg["model"]["backend"], "model": cfg["model"]["name"],
              "model_sha256": cfg["model"].get("digest"),
              "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
              "code_files_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                    for name in ["backend/app/llm/client.py", "backend/app/config.py", "scripts/smoke_vllm.py"]},
              "code_commit": commit, "code_dirty": dirty, "resolved_config_sha256": hashlib.sha256(resolved).hexdigest(),
              "host": socket.gethostname(), "platform": platform.platform(), "python": platform.python_version(),
              "software": software, "baseline_gate_passed": False,
              "limitations": ["Before/after VRAM is not peak VRAM", "One run is not p50/p95",
                              "Transport sidecars are not complete S5/S6 pipeline traces"], "results": results}
    (output / "resolved_config.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return all(row["passed_transport"] for row in results)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("counts", nargs="*", type=int)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    config = load_config()
    name = "smoke-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex
    output = args.out or ROOT / "eval" / "runs" / name
    passed = run_smoke(config, args.counts or [config["sampling"]["n_samples"]], output)
    print(f"Bukti: {output}; transport {'LULUS' if passed else 'BELUM LULUS'}. G3 tidak diluluskan otomatis.")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
