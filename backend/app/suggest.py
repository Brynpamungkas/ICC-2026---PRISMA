"""User-facing suggestion texts for TAHAN (Tabel A-3). Indonesian; built only from catalog metadata."""
from __future__ import annotations

from backend.app.catalog import Catalog


def _fmt(items: list[str]) -> str:
    return ", ".join(items)


def suggestion(reason: str, cat: Catalog, *, candidates: list[str] | None = None, unresolved: list[str] | None = None,
               period: str | None = None, regions: list[str] | None = None) -> str:
    if reason == "T1":
        return f"Contoh istilah yang dikenali: {_fmt(cat.example_terms())}."
    if reason == "T2":
        if unresolved:
            return (f"Bagian ini tidak dikenali: {_fmt(unresolved)}. Sebutkan nama provinsi resmi (mis. DKI Jakarta) "
                    "dan bulan lengkap dengan tahun (mis. September 2025).")
        metas = [cat.indicators[c] for c in (candidates or []) if c in cat.indicators]
        periods = sorted({p for m in metas for p in m.periods})
        txt = f"Periode tersedia untuk indikator terkait: {_fmt(periods)}." if periods else ""
        if period:
            txt = f"Periode {period} tidak tersedia. " + txt
        return txt.strip() or "Periksa periode dan wilayah yang tersedia pada Katalog Data."
    if reason == "T3":
        return "Persentase tidak bisa dijumlahkan. Gunakan rata-rata, atau tanyakan indikator berupa jumlah."
    if reason == "T4":
        return "Coba rumuskan pertanyaan dengan lebih sederhana."
    if reason == "T5":
        return "Periksa nama wilayah dan periode yang kamu sebut."
    return "Layanan pendukung sedang tidak tersedia. Coba lagi sebentar lagi."
