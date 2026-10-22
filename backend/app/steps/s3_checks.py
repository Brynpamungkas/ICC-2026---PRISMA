"""Langkah 3: pemeriksaan pi (periode), omega (wilayah), sigma (operasi vs satuan), persamaan (2).
`checks` mengembalikan (K_prime, kode_alasan) dengan kode_alasan None | "T2" | "T3".

PROPOSED (belum dibekukan; D05 BLOCKED BY K-01/K-18):
- Periode default = periode terbaru yang tersedia bagi SELURUH kandidat K (irisan, bacaan harfiah paper III-C,
  config decision.default_period=latest_intersection). Bila irisan kosong -> pi gagal untuk semua kandidat -> T2.
  Opsi lain (irisan setelah omega/sigma) memberi hasil berbeda pada kasus campuran (EDGE-03).
- K' kosong: T3 hanya bila SEMUA kandidat gugur semata karena sigma; selain itu T2 (diagnosis campuran, K-18).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.catalog import Catalog, get_catalog
from backend.app.config import load_config
from backend.app.schemas import Candidate, ExtractionResult


@dataclass
class CheckOutcome:
    k_prime: list[Candidate]
    reason: str | None
    period: str | None                         # periode yang dipakai (eksplisit atau default), None bila tak terselesaikan
    failures: dict[str, set[str]] = field(default_factory=dict)   # kode -> {"pi","omega","sigma","unresolved"}


def resolve_period(extraction: ExtractionResult, k: list[Candidate], cat: Catalog, config: dict | None = None) -> str | None:
    p = extraction.period
    if p and len(p) != 4:
        return p                                # periode yang diminta tidak pernah diganti menjadi terbaru (ALG-10)
    common = None
    for c in k:
        periods = set(cat.indicators[c.code].periods)
        common = periods if common is None else common & periods
    common = common or set()
    if p:                                       # tahun saja (USULAN K-18, 21 Okt): periode terbaru DI TAHUN ITU pada irisan K
        if (config or load_config())["decision"].get("year_only_period") != "latest_in_year_intersection":
            return p                            # perilaku lama: "2025" tidak cocok YYYY-MM -> pi gagal -> T2
        in_year = {x for x in common if x.startswith(p + "-")}
        return max(in_year) if in_year else p   # tak ada periode di tahun itu -> tetap "2025" -> T2 (tidak pindah tahun)
    return max(common) if common else None      # YYYY-MM: urutan leksikografis = kronologis


def check_candidates(extraction: ExtractionResult, k: list[Candidate], *, catalog: Catalog | None = None,
                     config: dict | None = None) -> CheckOutcome:
    cat = catalog or get_catalog()
    non_additive = set((config or load_config())["catalog"]["non_additive_units"])
    if extraction.unresolved:
        return CheckOutcome([], "T2", extraction.period, {c.code: {"unresolved"} for c in k})
    period = resolve_period(extraction, k, cat, config)
    kept: list[Candidate] = []
    failures: dict[str, set[str]] = {}
    for c in k:
        m = cat.indicators[c.code]
        bad: set[str] = set()
        if period is None or period not in m.periods:
            bad.add("pi")
        if extraction.regions and not set(extraction.regions) <= m.regions:
            bad.add("omega")
        if extraction.operation == "SUM" and m.unit in non_additive:
            bad.add("sigma")
        if bad:
            failures[c.code] = bad
        else:
            kept.append(c)
    if kept:
        return CheckOutcome(kept, None, period, failures)
    kinds = set().union(*failures.values()) if failures else set()
    return CheckOutcome([], "T3" if kinds == {"sigma"} else "T2", period, failures)


def checks(extraction: ExtractionResult, k: list[Candidate], *, catalog: Catalog | None = None,
           config: dict | None = None) -> tuple[list[Candidate], str | None]:
    out = check_candidates(extraction, k, catalog=catalog, config=config)
    return out.k_prime, out.reason
