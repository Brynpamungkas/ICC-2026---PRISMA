"""Read-only view of the semantic catalog (data/katalog/*.csv). Source of truth for S1-S3 (D04).

Nothing here is invented: every field comes from the CSV files that the data owner validated with
scripts/build_catalog.py --validate."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from backend.app.config import ROOT, ConfigError, load_config
from backend.app.schemas import Candidate
from backend.app.text import normalize_term


@dataclass(frozen=True)
class IndicatorMeta:
    code: str
    name: str
    definition: str
    unit: str
    source: str
    regions: frozenset[str]
    periods: frozenset[str]


@dataclass
class Catalog:
    indicators: dict[str, IndicatorMeta]                      # catalog order is the deterministic candidate order
    provinces: dict[str, str]                                 # code -> name
    kamus: dict[tuple[str, ...], dict[str, set[str]]] = field(default_factory=dict)   # term tokens -> {jenis: codes}
    operations: dict[tuple[str, ...], str] = field(default_factory=dict)              # lexicon phrase tokens -> operation
    version: str | None = None

    def candidate(self, code: str) -> Candidate:
        m = self.indicators[code]
        return Candidate(code=m.code, canonical_name=m.name, unit=m.unit)

    def example_terms(self, limit: int = 5) -> list[str]:
        names = [m.name.casefold() for m in self.indicators.values()]
        if len(names) <= limit:
            return names
        step = len(names) / limit
        return [names[int(i * step)] for i in range(limit)]


def _rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_catalog(katalog_dir: Path | str | None = None) -> Catalog:
    d = Path(katalog_dir) if katalog_dir else ROOT / load_config()["catalog"]["dir"]
    if not d.is_absolute():
        d = ROOT / d
    indicators: dict[str, IndicatorMeta] = {}
    for r in _rows(d / "indikator.csv"):
        try:
            regions = frozenset(json.loads(r["cakupan_wilayah"]))
            periods = frozenset(json.loads(r["periode_tersedia"]))
        except (ValueError, TypeError) as exc:
            raise ConfigError(f"indikator.csv {r['kode']}: cakupan_wilayah/periode_tersedia bukan JSON (jalankan build_catalog.py --validate)") from exc
        indicators[r["kode"]] = IndicatorMeta(r["kode"], r["nama_kanonik"], r["definisi_resmi"], r["satuan"],
                                              r["sumber"], regions, periods)
    provinces = {r["kode"]: r["nama"] for r in _rows(d / "provinsi.csv")}
    cat = Catalog(indicators=indicators, provinces=provinces)
    for r in _rows(d / "kamus_istilah.csv"):
        key = tuple(normalize_term(r["istilah"]).split(" "))
        cat.kamus.setdefault(key, {}).setdefault(r["jenis"], set()).add(r["kode"])
    for r in _rows(d / "operasi.csv"):
        cat.operations[tuple(normalize_term(r["kata"]).split(" "))] = r["operasi"]
    vf = d / "VERSION"
    if vf.exists():
        cat.version = json.loads(vf.read_text(encoding="utf-8")).get("catalog_hash")
    return cat


@lru_cache(maxsize=4)
def _cached(path: str) -> Catalog:
    return load_catalog(path)


def get_catalog(katalog_dir: Path | str | None = None) -> Catalog:
    d = Path(katalog_dir) if katalog_dir else ROOT / load_config()["catalog"]["dir"]
    return _cached(str(d if d.is_absolute() else ROOT / d))
