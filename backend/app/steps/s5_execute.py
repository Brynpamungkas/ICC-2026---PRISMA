"""Langkah 5: ikat tiap kerangka valid ke tiap kandidat K' dan eksekusi. Semua hasil sukses-kosong -> T5 (orkestrator).
Satu kerangka dieksekusi untuk SEMUA kandidat (perbedaan antarkandidat hanya dari interpretasi). Galat/timeout/terpotong
dipertahankan sebagai status pada ExecResult.error, tidak dibuang dan tidak dianggap kosong (K-16)."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import time

from backend.app.catalog import Catalog, get_catalog
from backend.app.schemas import Candidate, ExecResult, ExtractionResult, SqlSkeleton
from backend.app.sqlguard.executor import run_query

TEXT_COLUMNS = {"wilayah", "periode"}


def bind_params(code: str, extraction: ExtractionResult) -> dict:
    params = {"indikator": code, "periode": extraction.period}
    params.update({f"wilayah_{i}": r for i, r in enumerate(extraction.regions)})
    return params


def execute_all(skeletons: list[SqlSkeleton], k_prime: list[Candidate], extraction: ExtractionResult, *,
                db_path: str | Path | None = None, catalog: Catalog | None = None,
                observer: Callable[[dict], None] | None = None) -> list[list[ExecResult]]:
    """Satu daftar per kerangka VALID (urutan sampel asli), tiap daftar berurutan sama dengan k_prime."""
    cat = catalog or get_catalog()
    results = []
    for sample_position, sk in enumerate(skeletons):
        if not sk.valid:
            continue
        row = []
        for candidate_position, c in enumerate(k_prime):
            params = bind_params(c.code, extraction)
            started_at = datetime.now(timezone.utc).isoformat()
            started = time.perf_counter()
            try:
                raw = run_query(sk.sql, params, db_path=db_path)
            except Exception as exc:
                if observer is not None:
                    observer({"sample_position": sample_position, "candidate_position": candidate_position,
                              "candidate_code": c.code, "parameters": params, "started_at": started_at,
                              "duration_ms": (time.perf_counter() - started) * 1000,
                              "error_category": type(exc).__name__})
                raise
            elapsed_ms = (time.perf_counter() - started) * 1000
            structure = "TEXT" if extraction.operation == "RANK" and TEXT_COLUMNS & set(raw.columns) else "NUMBER"
            result = ExecResult(candidate_code=c.code, columns=raw.columns, rows=raw.rows, structure=structure,
                                unit=cat.indicators[c.code].unit, error=raw.error)
            row.append(result)
            if observer is not None:
                observer({"sample_position": sample_position, "candidate_position": candidate_position,
                          "candidate_code": c.code, "parameters": params, "started_at": started_at,
                          "duration_ms": elapsed_ms, "sql_sha256": hashlib.sha256(sk.sql.encode()).hexdigest(),
                          "result": result.model_dump()})
        results.append(row)
    return results
