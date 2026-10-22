"""Langkah 2: resolusi katalog, persamaan (1): K(q) = union indikator dari seluruh pasangan (istilah, indikator).
Kosong -> T1 (diputuskan orkestrator). Urutan = urutan indikator.csv (deterministik; K-15/K-17)."""
from __future__ import annotations

from backend.app.catalog import Catalog, get_catalog
from backend.app.schemas import Candidate, ExtractionResult


def resolve(extraction: ExtractionResult, *, catalog: Catalog | None = None) -> list[Candidate]:
    cat = catalog or get_catalog()
    codes: set[str] = set()
    for term in extraction.terms:
        codes |= cat.kamus.get(tuple(term.split(" ")), {}).get("indikator", set())
    return [cat.candidate(c) for c in cat.indicators if c in codes]
