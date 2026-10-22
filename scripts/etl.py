"""ETL PRISMA: data/raw_bps (+ manifest.yaml) -> data/prisma.sqlite (skema Tabel A-1). Idempoten.

Prinsip (AGENTS.md / D04 sec. 7): tidak ada data BPS yang dikarang; kode/provinsi tak dikenal,
duplikat PK, dan nilai non-numerik yang tidak dinyatakan di `null_symbols` dilaporkan sebagai
error dan MEMBATALKAN build (DB lama tidak ditimpa). Simbol tak-tersedia dipetakan ke NULL hanya
bila pemilik data menuliskannya di manifest (K-16 OPEN).

Pemakaian:
  python scripts/etl.py --inspect data/raw_bps/berkas.xlsx [--sheet 0]   # lihat grid + indeks kolom
  python scripts/etl.py --draft                                           # tahan placeholder katalog -> data/prisma.draft.sqlite
  python scripts/etl.py                                                   # build final -> data/prisma.sqlite
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_lib as cl  # noqa: E402

RAW_DIR = cl.ROOT / "data" / "raw_bps"
KATALOG_DIR = cl.KATALOG_DIR  # tes me-monkeypatch RAW_DIR / KATALOG_DIR
DEFAULT_NULL_SYMBOLS: list[str] = []  # sengaja kosong: simbol harus dinyatakan pemilik data di manifest


class EtlError(Exception):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_grid(path: Path, sheet=0) -> pd.DataFrame:
    """Read a raw table as a string grid with no header inference."""
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm", ".xls"):
        return pd.read_excel(path, sheet_name=sheet, header=None, dtype=str)
    if suffix in (".csv", ".tsv"):
        sep = "\t" if suffix == ".tsv" else None
        return pd.read_csv(path, header=None, dtype=str, sep=sep, engine="python", encoding="utf-8-sig")
    raise EtlError(f"format berkas tidak didukung: {path.name}")


def cell(grid: pd.DataFrame, r: int, c: int) -> str:
    v = grid.iat[r, c]
    return "" if pd.isna(v) else str(v).strip()


def joined_headers(grid: pd.DataFrame, header_rows: list[int]) -> list[str]:
    """Join multi-row headers with ' | '; merged cells (blank) are forward-filled to the right."""
    n_cols = grid.shape[1]
    parts: list[list[str]] = []
    for hr in header_rows:
        row, last = [], ""
        for c in range(n_cols):
            v = cell(grid, hr, c)
            if v:
                last = v
            row.append(" ".join((v or last).split()))
        parts.append(row)
    return [" | ".join(p[c] for p in parts if p[c]) for c in range(n_cols)]


def parse_value(raw: str, null_symbols: set[str], decimal: str) -> float | None:
    s = raw.strip()
    if s == "" or s in null_symbols:
        return None
    if decimal == ",":
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "") if s.count(",") and "." in s else s
    return float(s)  # ValueError dilaporkan pemanggil


def norm_prov(name: str) -> str:
    n = cl.normalize_term(name)
    for prefix in ("provinsi ", "prov "):
        if n.startswith(prefix):
            n = n[len(prefix):]
    return n


def province_lookup(prov_rows: list[dict], aliases: dict[str, str]) -> dict[str, str]:
    by_norm = {norm_prov(r["nama"]): r["kode"].strip() for r in prov_rows}
    lookup = dict(by_norm)
    for alias, target in (aliases or {}).items():
        t = norm_prov(target)
        if t not in by_norm:
            raise EtlError(f"province_aliases: target {target!r} tidak ada di provinsi.csv")
        lookup[norm_prov(alias)] = by_norm[t]
    return lookup


def match_province(name: str, lookup: dict[str, str]) -> str | None:
    return lookup.get(norm_prov(name))


def extract_source(src: dict, manifest: dict, lookup: dict[str, str], known_inds: set[str]) -> tuple[list[tuple], dict, list[str]]:
    """Return (facts, stats, errors). facts = (kode_provinsi, kode_indikator, periode, nilai)."""
    errors: list[str] = []
    path = RAW_DIR / src["file"]
    if not path.exists():
        return [], {}, [f"{src['file']}: berkas tidak ditemukan di data/raw_bps/"]
    grid = read_grid(path, src.get("sheet", 0))
    null_symbols = set(manifest.get("null_symbols", DEFAULT_NULL_SYMBOLS))
    skip_names = {cl.normalize_term(x) for x in manifest.get("skip_names", [])}
    decimal = src.get("decimal", manifest.get("decimal", "."))
    fmt = src.get("format", "wide")
    facts: list[tuple] = []
    stats = {"file": src["file"], "sha256": sha256_file(path), "rows_read": 0, "facts": 0,
             "null_values": 0, "skipped_names": 0, "footer_rows": 0}

    def col_index(spec, headers: list[str] | None) -> int:
        if isinstance(spec, int):
            return spec
        if headers is None:
            raise EtlError(f"{src['file']}: kolom {spec!r} butuh header_rows")
        matches = [i for i, h in enumerate(headers) if " ".join(h.split()) == " ".join(str(spec).split())]
        if len(matches) != 1:
            raise EtlError(f"{src['file']}: header {spec!r} cocok {len(matches)} kolom; gunakan `col` (indeks) atau header lengkap. "
                           f"Jalankan --inspect untuk melihat header gabungan.")
        return matches[0]

    try:
        header_rows = src.get("header_rows", [])
        headers = joined_headers(grid, header_rows) if header_rows else None
        first = src.get("first_data_row", (max(header_rows) + 1) if header_rows else 0)
        pcol = col_index(src["province_col"], headers)
        if fmt == "wide":
            targets = []
            for spec in src["columns"]:
                idx = col_index(spec["col"] if "col" in spec else spec["header"], headers)
                if spec["kode_indikator"] not in known_inds:
                    raise EtlError(f"{src['file']}: kode_indikator {spec['kode_indikator']!r} tidak ada di indikator.csv")
                targets.append((idx, spec["kode_indikator"], str(spec["periode"])))
        elif fmt == "long":
            if src["kode_indikator"] not in known_inds:
                raise EtlError(f"{src['file']}: kode_indikator {src['kode_indikator']!r} tidak ada di indikator.csv")
            pidx = col_index(src["period_col"], headers)
            vidx = col_index(src["value_col"], headers)
        else:
            raise EtlError(f"{src['file']}: format {fmt!r} tidak dikenal (wide|long)")
    except (EtlError, KeyError) as exc:
        return [], stats, [str(exc) if isinstance(exc, EtlError) else f"{src['file']}: kunci manifest hilang {exc}"]

    for r in range(first, grid.shape[0]):
        name = cell(grid, r, pcol)
        if not name:
            continue
        stats["rows_read"] += 1
        if cl.normalize_term(name) in skip_names:
            stats["skipped_names"] += 1
            continue
        kode_prov = match_province(name, lookup)
        if kode_prov is None:
            others = [cell(grid, r, c) for c in range(grid.shape[1]) if c != pcol]
            if not any(others):
                stats["footer_rows"] += 1  # baris catatan/sumber tanpa angka
                continue
            errors.append(f"{src['file']} baris {r + 1}: provinsi {name!r} tidak dikenal (tambahkan province_aliases atau skip_names)")
            continue
        pairs = ([(ind, per, cell(grid, r, idx)) for idx, ind, per in targets] if fmt == "wide"
                 else [(src["kode_indikator"], cell(grid, r, pidx), cell(grid, r, vidx))])
        for ind, per, raw in pairs:
            if not per:
                errors.append(f"{src['file']} baris {r + 1}: periode kosong")
                continue
            try:
                val = parse_value(raw, null_symbols, decimal)
            except ValueError:
                errors.append(f"{src['file']} baris {r + 1} ({name}): nilai {raw!r} bukan angka dan bukan simbol di null_symbols")
                continue
            if val is None:
                stats["null_values"] += 1
            facts.append((kode_prov, ind, per, val))
            stats["facts"] += 1
    return facts, stats, errors


def logical_hash(conn: sqlite3.Connection) -> str:
    h = hashlib.sha256()
    for table, order in [("provinsi", "kode"), ("indikator", "kode"),
                         ("kamus_istilah", "istilah, jenis, kode"),
                         ("nilai_indikator", "kode_provinsi, kode_indikator, periode")]:
        for row in conn.execute(f"SELECT * FROM {table} ORDER BY {order}"):
            h.update(json.dumps(row, ensure_ascii=False).encode())
        h.update(b"|")
    return h.hexdigest()


def provenance_listed(sumber_md: Path, files: list[str]) -> list[str]:
    text = sumber_md.read_text(encoding="utf-8") if sumber_md.exists() else ""
    return [f for f in files if f not in text]


def build(draft: bool, manifest_path: Path, out_db: Path, report_path: Path) -> int:
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not manifest_path.exists():
        print(f"Manifest tidak ada: {manifest_path}\nSalin data/raw_bps/manifest.example.yaml -> manifest.yaml lalu isi.")
        return 1
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    sources = manifest.get("sources") or []
    errors, warnings = cl.validate_catalog(KATALOG_DIR, allow_placeholders=draft)
    if errors:
        print("Katalog belum valid (jalankan scripts/build_catalog.py --validate):")
        for e in errors:
            print("  -", e)
        return 1
    prov_rows = cl.read_csv(KATALOG_DIR / "provinsi.csv", cl.HEADERS["provinsi.csv"])
    ind_rows = cl.read_csv(KATALOG_DIR / "indikator.csv", cl.HEADERS["indikator.csv"])
    known_inds = {r["kode"].strip() for r in ind_rows}
    try:
        lookup = province_lookup(prov_rows, manifest.get("province_aliases", {}))
    except EtlError as exc:
        print(exc)
        return 1

    all_facts: list[tuple] = []
    src_stats: list[dict] = []
    for src in sources:
        facts, stats, errs = extract_source(src, manifest, lookup, known_inds)
        errors += errs
        all_facts += [(f, src["file"]) for f in facts]
        if stats:
            src_stats.append(stats)

    seen: dict[tuple, str] = {}
    unique: list[tuple] = []
    for f, fname in all_facts:
        key = f[:3]
        if key in seen:
            errors.append(f"duplikat PK {key}: {seen[key]} dan {fname} (tidak ditimpa/dijumlah otomatis)")
        else:
            seen[key] = fname
            unique.append(f)

    tmp = out_db.with_name(out_db.name + ".tmp")
    if tmp.exists():
        tmp.unlink()
    report = {"status": "DRAFT" if draft else "FINAL-CANDIDATE", "started_utc": started, "errors": errors,
              "warnings": warnings, "sources": src_stats, "catalog_version": cl.compute_version(KATALOG_DIR)}
    if not errors:
        conn = sqlite3.connect(tmp)
        try:
            cl.create_schema(conn)
            report["catalog_rows"] = cl.load_catalog(conn, KATALOG_DIR)
            conn.executemany("INSERT INTO nilai_indikator VALUES (?,?,?,?)", unique)
            conn.commit()
            bad = conn.execute("PRAGMA foreign_key_check").fetchall()
            if bad:
                errors.append(f"foreign_key_check gagal: {bad[:5]}")
            report["fact_rows"] = len(unique)
            report["logical_hash"] = logical_hash(conn)
            cov: dict[str, dict] = {}
            for ind, prov, per in conn.execute("SELECT kode_indikator, kode_provinsi, periode FROM nilai_indikator WHERE nilai IS NOT NULL"):
                c = cov.setdefault(ind, {"provinsi": set(), "periode": set()})
                c["provinsi"].add(prov)
                c["periode"].add(per)
            report["observed_coverage"] = {k: {"n_provinsi": len(v["provinsi"]), "periode": sorted(v["periode"])} for k, v in sorted(cov.items())}
            for r in ind_rows:
                k = r["kode"].strip()
                if k not in cov:
                    warnings.append(f"indikator {k}: tidak ada observasi non-NULL di DB")
                    continue
                try:
                    declared_per = set(json.loads(r["periode_tersedia"]))
                    declared_cov = set(json.loads(r["cakupan_wilayah"]))
                except (ValueError, TypeError):
                    continue  # masih placeholder (mode draft)
                if declared_per != cov[k]["periode"] or declared_cov != cov[k]["provinsi"]:
                    warnings.append(f"indikator {k}: metadata cakupan/periode berbeda dari observasi DB (K-18; putuskan manual)")
        finally:
            conn.close()
    report["errors"], report["warnings"] = errors, warnings
    report["not_listed_in_sumber_md"] = provenance_listed(RAW_DIR / "sumber.md", [s["file"] for s in sources])
    if report["not_listed_in_sumber_md"]:
        warnings.append(f"berkas belum tercatat di data/raw_bps/sumber.md: {report['not_listed_in_sumber_md']}")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=list) + "\n", encoding="utf-8")
    if errors:
        if tmp.exists():
            tmp.unlink()
        print(f"ETL GAGAL ({len(errors)} error); DB lama tidak diubah. Lihat {report_path}")
        for e in errors[:25]:
            print("  -", e)
        return 1
    os.replace(tmp, out_db)
    print(f"ETL OK -> {out_db}  ({report['fact_rows']} fakta, hash logis {report['logical_hash'][:12]}...)")
    for w in warnings:
        print("  WARNING:", w)
    if draft:
        print("Mode DRAFT: bukan snapshot final / bukan bukti G1.")
    return 0


def inspect(path: Path, sheet) -> int:
    grid = read_grid(path, sheet)
    print(f"{path.name}: {grid.shape[0]} baris x {grid.shape[1]} kolom (indeks baris & kolom mulai dari 0)")
    for r in range(min(25, grid.shape[0])):
        print(f"[{r:>2}]", " | ".join(f"{c}:{cell(grid, r, c)[:22]}" for c in range(grid.shape[1]) if cell(grid, r, c)))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inspect", type=Path)
    ap.add_argument("--sheet", default=0)
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--manifest", type=Path, default=RAW_DIR / "manifest.yaml")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--report", type=Path, default=cl.ROOT / "data" / "etl_report.json")
    a = ap.parse_args(argv)
    if a.inspect:
        sheet = int(a.sheet) if str(a.sheet).isdigit() else a.sheet
        return inspect(a.inspect, sheet)
    out = a.out or (cl.ROOT / "data" / ("prisma.draft.sqlite" if a.draft else "prisma.sqlite"))
    return build(a.draft, a.manifest, out, a.report)


if __name__ == "__main__":
    sys.exit(main())
