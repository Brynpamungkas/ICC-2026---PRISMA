"""Optional private diagnostic JSONL; separate from the unchanged LogRecord API.

A run is complete only when its final event is ``complete``. Interrupted files
are evidence of incomplete work, never silently accepted or overwritten.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

from pydantic import BaseModel

from backend.app.config import ROOT


def _json_value(value):
    if isinstance(value, BaseModel):
        return value.model_dump()
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (set, frozenset)):
        # CheckOutcome.failures contains unordered reason sets. Order only these
        # sets for JSON; never sort result rows or sample/voting sequences.
        return sorted(value)
    raise TypeError(f"Unsupported trace value: {type(value).__name__}")


class PipelineTrace:
    def __init__(self, directory: str | Path | None, run_id: str):
        if not re.fullmatch(r"[0-9a-f]{32}", run_id):
            raise ValueError("Invalid internal run identifier")
        self.run_id = run_id
        self.sequence = 0
        self.path: Path | None = None
        if directory is not None:
            folder = ROOT / directory
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            path = folder / (run_id + ".trace.jsonl")
            os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
            self.path = path

    def emit(self, event: str, data: dict) -> None:
        if self.path is None:
            return
        payload = {"trace_schema": "local-pipeline-1", "run_id": self.run_id,
                   "sequence": self.sequence, "recorded_at": datetime.now(timezone.utc).isoformat(),
                   "event": event, "data": data}
        line = json.dumps(payload, ensure_ascii=False, allow_nan=False, default=_json_value) + "\n"
        # Do not recreate an externally removed run or append to another run's file.
        descriptor = os.open(self.path, os.O_WRONLY | os.O_APPEND)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(line)
            stream.flush()
            os.fsync(stream.fileno())
        self.sequence += 1
