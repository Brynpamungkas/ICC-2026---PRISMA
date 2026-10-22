"""Langkah 5: ikat tiap kerangka valid ke tiap kandidat K' dan eksekusi. Semua hasil sukses-kosong -> T5 (orkestrator).
Satu kerangka dieksekusi untuk SEMUA kandidat (perbedaan antarkandidat hanya dari interpretasi). Galat/timeout/terpotong
dipertahankan sebagai status pada ExecResult.error, tidak dibuang dan tidak dianggap kosong (K-16).

Struktur hasil (Tabel VII): "TEXT" hanya bila kolom teks ADALAH jawabannya, yaitu operasi RANK ("provinsi mana ...").
Pada pencarian nilai (NONE/SUM/AVG) kolom wilayah hanya label baris; jawabannya angka, jadi struktur "NUMBER" dan angkanya
dibandingkan (contoh paper Tabel VII: "Berapa angka kemiskinan Jawa Barat?" persen vs ribu jiwa -> tidak pernah setara).
Perbaikan 21 Okt: sebelumnya setiap hasil berkolom wilayah dianggap TEXT sehingga persen vs jumlah satu provinsi selalu JAWAB."""
from __future__ import annotations

from pathlib import Path

from backend.app.catalog import Catalog, get_catalog
from backend.app.schemas import Candidate, ExecResult, ExtractionResult, SqlSkeleton
from backend.app.sqlguard.executor import run_query

TEXT_COLUMNS = {"wilayah", "periode"}


def bind_params(code: str, extraction: ExtractionResult) -> dict:
    params = {"indikator": code, "periode": extraction.period}
    params.update({f"wilayah_{i}": r for i, r in enumerate(extraction.regions)})
    return params


def execute_all(skeletons: list[SqlSkeleton], k_prime: list[Candidate], extraction: ExtractionResult, *,
                db_path: str | Path | None = None, catalog: Catalog | None = None) -> list[list[ExecResult]]:
    """Satu daftar per kerangka VALID (urutan sampel asli), tiap daftar berurutan sama dengan k_prime."""
    cat = catalog or get_catalog()
    results = []
    for sk in skeletons:
        if not sk.valid:
            continue
        row = []
        for c in k_prime:
            raw = run_query(sk.sql, bind_params(c.code, extraction), db_path=db_path)
            structure = "TEXT" if extraction.operation == "RANK" and TEXT_COLUMNS & set(raw.columns) else "NUMBER"
            row.append(ExecResult(candidate_code=c.code, columns=raw.columns, rows=raw.rows, structure=structure,
                                  unit=cat.indicators[c.code].unit, error=raw.error))
        results.append(row)
    return results
