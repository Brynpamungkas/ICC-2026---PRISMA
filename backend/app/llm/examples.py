"""Contoh few-shot prompt (PRM-09/PRM-10): hanya soal DEV, dibaca dari config prompt.examples_file, diambil few_shot_k
pertama dalam urutan file (deterministik). Sama untuk K1/K2/K3 (K-08). Tanpa file -> daftar kosong (perilaku v0.2.3).
Konteks tiap contoh dihitung dari S1 atas teks contoh, sehingga formatnya identik dengan EXTRACTION_CONTEXT soal yang ditanya."""
from __future__ import annotations

import json

from backend.app.config import ROOT, ConfigError


def load_examples(config: dict) -> list[dict]:
    p = config["prompt"].get("examples_file")
    if not p:
        return []
    path = ROOT / p
    if not path.exists():
        raise ConfigError(f"prompt.examples_file tidak ditemukan: {p}")
    from backend.app.llm.prompt import extraction_context
    from backend.app.steps.s1_extract import extract
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for e in data["contoh"][: int(config["prompt"]["few_shot_k"])]:
        out.append({**e, "context": extraction_context(extract(e["question"], config=config))})
    return out
