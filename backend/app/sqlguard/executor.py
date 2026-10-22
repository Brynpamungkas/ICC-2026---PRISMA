"""Eksekutor aman: SQLite mode=ro, PRAGMA query_only, batas 2 detik dan 1.000 baris, parameter terikat.
Nilai config dibaca dari config.yaml (execution.*). Galat/timeout/terpotong TIDAK disamakan dengan hasil kosong (D05 ALG-18)."""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from backend.app.config import ROOT, load_config


class DatabaseUnavailable(Exception):
    """Basis data tidak dapat dibuka (kegagalan layanan, bukan galat SQL kerangka)."""


@dataclass
class RawResult:
    columns: list[str]
    rows: list[list]
    error: str | None = None          # None | "TIMEOUT" | "TRUNCATED" | "SQL_ERROR: ..."


def _plain(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v


def run_query(sql: str, params: dict, *, db_path: str | Path | None = None, timeout_s: float | None = None,
              max_rows: int | None = None) -> RawResult:
    ex = load_config()["execution"]
    path = Path(db_path or ex["db_path"])
    path = path if path.is_absolute() else ROOT / path
    timeout_s = ex["timeout_s"] if timeout_s is None else timeout_s
    max_rows = ex["max_rows"] if max_rows is None else max_rows
    if not path.exists():
        raise DatabaseUnavailable(f"basis data tidak ditemukan: {path.name}")
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        conn.execute("PRAGMA query_only = ON")
    except sqlite3.Error as exc:
        raise DatabaseUnavailable(str(exc)) from exc
    deadline = time.monotonic() + timeout_s
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 1000)
    try:
        cur = conn.execute(sql, params)
        columns = [d[0] for d in cur.description] if cur.description else []
        fetched = cur.fetchmany(max_rows + 1)
        rows = [[_plain(v) for v in r] for r in fetched[:max_rows]]
        return RawResult(columns, rows, "TRUNCATED" if len(fetched) > max_rows else None)   # tepat max_rows != terpotong (K-16)
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            return RawResult([], [], "TIMEOUT")
        return RawResult([], [], f"SQL_ERROR: {exc}")
    except sqlite3.Error as exc:
        return RawResult([], [], f"SQL_ERROR: {exc}")
    finally:
        conn.close()
