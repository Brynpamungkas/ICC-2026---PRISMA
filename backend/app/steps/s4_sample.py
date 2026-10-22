"""Langkah 4: bangkitkan N kerangka SQL dari SLM lalu validasi. Semua kosong -> T4 (diputuskan orkestrator).
Satu-satunya langkah yang memanggil model. Indeks asli sampel dipertahankan; kerangka tidak valid dicatat dengan alasan,
tidak diperbaiki dan tidak diganti sampel baru."""
from __future__ import annotations

import re

from backend.app.catalog import Catalog, get_catalog
from backend.app.llm.prompt import build_prompt, extraction_context
from backend.app.schemas import ExtractionResult, SqlSkeleton
from backend.app.sqlguard.validator import validate_sql

_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.S | re.I)


def parse_output(text: str) -> str:
    m = _FENCE.search(text)
    return (m.group(1) if m else text).strip()


def sample_skeletons(question: str, extraction: ExtractionResult, n: int, *, llm, catalog: Catalog | None = None,
                     examples: list[dict] | None = None) -> list[SqlSkeleton]:
    cat = catalog or get_catalog()
    prompt = build_prompt(question, "", examples or [], extraction_context(extraction))
    codes = set(cat.indicators)
    out = []
    for raw in llm.generate(prompt, n):
        sql = parse_output(raw)
        ok, why = validate_sql(sql, forbidden_literals=codes, region_count=len(extraction.regions),
                            shape=(extraction.operation, extraction.rank_direction, extraction.top_n))
        out.append(SqlSkeleton(sql=sql, valid=ok, reject_reason=why))
    return out
