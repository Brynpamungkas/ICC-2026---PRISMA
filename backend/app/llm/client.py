"""Klien model. Dua backend dengan antarmuka yang sama, dipilih dari config (model.backend):
  - vllm   : API kompatibel OpenAI, satu permintaan n sampel (utama, sesuai paper)
  - ollama : cadangan; n sampel lewat beberapa permintaan (laporkan terpisah)
Kegagalan koneksi/respons kosong -> LlmUnavailable (orkestrator: TAHAN berkode layanan, K-06). Tidak ada sampel palsu.
Pesan dikirim sebagai system (SYS-SQL-A) + user (USR-SQL-A), D06 PRM-05."""
from __future__ import annotations

import requests

from backend.app.config import load_config
from backend.app.llm.prompt import build_messages


class LlmUnavailable(Exception):
    pass


class LlmClient:
    def __init__(self, config: dict | None = None, timeout_s: float = 120.0):
        cfg = config or load_config()
        self.cfg = cfg
        self.backend = cfg["model"]["backend"]
        self.timeout_s = timeout_s
        self.model_name = cfg["model"]["name"] if self.backend == "vllm" else cfg["model"]["fallback"]["name"]

    def generate(self, prompt: str, n: int, system: str | None = None) -> list[str]:
        s = self.cfg["sampling"]
        try:
            if self.backend == "vllm":
                r = requests.post(self.cfg["model"]["url"], timeout=self.timeout_s, json={
                    "model": self.cfg["model"]["name"], "messages": build_messages(prompt, system), "n": n,
                    "max_tokens": s["max_output_tokens"], "temperature": s["temperature"], "top_p": s["top_p"], "seed": s["seed"]})
                r.raise_for_status()
                out = [c["message"]["content"] for c in r.json()["choices"]]
            else:
                fb = self.cfg["model"]["fallback"]
                out = []
                for i in range(n):
                    r = requests.post(fb["url"], timeout=self.timeout_s, json={
                        "model": fb["name"], "stream": False, "messages": build_messages(prompt, system),
                        "options": {"temperature": s["temperature"], "top_p": s["top_p"], "seed": s["seed"] + i,
                                    "num_predict": s["max_output_tokens"]}})
                    r.raise_for_status()
                    out.append(r.json()["message"]["content"])
        except (requests.RequestException, KeyError, ValueError) as exc:
            raise LlmUnavailable(str(exc)[:120]) from exc
        if not out:
            raise LlmUnavailable("model tidak mengembalikan sampel")
        return out          # bisa < n (EDGE-34): dicatat apa adanya, tidak diisi sampel palsu
