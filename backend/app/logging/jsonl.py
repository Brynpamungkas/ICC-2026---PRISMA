"""Penulis log JSONL (satu baris per pertanyaan, LogRecord). Langkah yang dilewati tidak dicatat sebagai 0 ms."""
from pathlib import Path

from backend.app.config import ROOT
from backend.app.schemas import LogRecord


def write_log(record: LogRecord, path: str) -> None:
    p = Path(path)
    p = p if p.is_absolute() else ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(record.model_dump_json() + "\n")
