"""Explicit model transport. Preserve samples and optional raw HTTP evidence.

vLLM and llama.cpp use OpenAI-compatible completions. Legacy Ollama is never
selected automatically. Sidecars are transport evidence, not full S5/S6 traces.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile
import time
from uuid import uuid4

import requests

from backend.app.config import ROOT, ConfigError, load_config
from backend.app.llm.prompt import build_messages


class LlmUnavailable(Exception):
    """Model transport, protocol, or required evidence storage failed."""


class LlmClient:
    def __init__(self, config: dict | None = None, timeout_s: float | None = None):
        self.cfg = load_config() if config is None else config
        self.backend = self.cfg["model"]["backend"]
        if self.backend not in {"vllm", "llama_cpp", "ollama"}:
            raise ConfigError("Backend model tidak dikenal; tidak ada penggantian otomatis.")
        self.timeout_s = self.cfg["transport"]["timeout_s"] if timeout_s is None else timeout_s
        if (isinstance(self.timeout_s, bool) or not isinstance(self.timeout_s, (int, float))
                or not math.isfinite(self.timeout_s) or self.timeout_s <= 0):
            raise ConfigError("Batas waktu HTTP harus bernilai positif dan berhingga.")
        self.model_name = (self.cfg["model"]["fallback"]["name"] if self.backend == "ollama"
                           else self.cfg["model"]["name"])
        self.last_trace_path: Path | None = None

    def is_ready(self) -> bool:
        """Probe health and identity, without generating a sample."""
        api = self.cfg["api"]
        try:
            response = requests.get(api["model_health_url"], timeout=api["health_timeout_s"], allow_redirects=False)
            if response.status_code != 200:
                return False
            models = requests.get(api["model_list_url"], timeout=api["health_timeout_s"], allow_redirects=False)
            models.raise_for_status()
            return self.model_name in {item["id"] for item in models.json()["data"]}
        except (requests.RequestException, KeyError, TypeError, ValueError):
            return False

    def _archive(self, record: dict) -> None:
        self.last_trace_path = None
        directory = self.cfg["transport"]["trace_dir"]
        if directory is None:
            return
        folder = ROOT / directory
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = folder / (record["call_id"] + ".json")
        descriptor, name = tempfile.mkstemp(prefix=".pending-", dir=folder)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(record, stream, indent=2, ensure_ascii=False, allow_nan=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        self.last_trace_path = target

    def generate(self, prompt: str, n: int, system: str | None = None) -> list[str]:
        if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
            raise ValueError("Jumlah sampel harus bilangan bulat positif.")
        s = self.cfg["sampling"]
        payload = {"model": self.model_name, "messages": build_messages(prompt, system), "n": n,
                   "max_tokens": s["max_output_tokens"], "temperature": s["temperature"],
                   "top_p": s["top_p"], "seed": s["seed"]}
        trace = {"schema_version": "transport-1", "call_id": str(uuid4()), "backend": self.backend,
                 "recorded_at": datetime.now(timezone.utc).isoformat(), "model": self.model_name,
                 "request": payload, "response": None, "attempts": [], "requested_n": n,
                 "received_n": 0, "status": "FAILED"}
        out: list[str] = []
        failure: Exception | None = None
        started = time.monotonic()
        try:
            if self.backend in {"vllm", "llama_cpp"}:
                r = requests.post(self.cfg["model"]["url"], timeout=self.timeout_s, json=payload)
                trace.update(http_status=getattr(r, "status_code", None), response_text=getattr(r, "text", None))
                r.raise_for_status()
                data = r.json()
                trace["response"] = data
                if not isinstance(data, dict) or not isinstance(data.get("choices"), list) or not data["choices"]:
                    raise ValueError("invalid choices")
                for choice in data["choices"]:
                    content = choice["message"]["content"]
                    if not isinstance(content, str):
                        raise ValueError("invalid content")
                    out.append(content)
            else:
                fb = self.cfg["model"]["fallback"]
                for i in range(n):
                    body = {
                        "model": fb["name"], "stream": False, "messages": build_messages(prompt, system),
                        "options": {"temperature": s["temperature"], "top_p": s["top_p"], "seed": s["seed"] + i,
                                    "num_predict": s["max_output_tokens"]}}
                    attempt = {"sample_index": i, "request": body, "response": None}
                    trace["attempts"].append(attempt)
                    r = requests.post(fb["url"], timeout=self.timeout_s, json=body)
                    attempt.update(http_status=getattr(r, "status_code", None), response_text=getattr(r, "text", None))
                    r.raise_for_status()
                    attempt["response"] = r.json()
                    content = attempt["response"]["message"]["content"]
                    if not isinstance(content, str):
                        raise ValueError("invalid content")
                    out.append(content)
            trace["status"] = "COMPLETE" if len(out) == n else "PARTIAL" if len(out) < n else "SURPLUS"
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            trace["error_category"] = type(exc).__name__
            failure = exc
        finally:
            trace["received_n"] = len(out)
            trace["duration_s"] = time.monotonic() - started
            try:
                self._archive(trace)
            except (OSError, ValueError, TypeError) as exc:
                raise LlmUnavailable("Bukti respons model belum dapat disimpan.") from exc
        if failure is not None:
            raise LlmUnavailable("Layanan model belum memberikan respons yang sah.") from failure
        return out  # EDGE-34: retain wire order and duplicates, even when fewer than n.
