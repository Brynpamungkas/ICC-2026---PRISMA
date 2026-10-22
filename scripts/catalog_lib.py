"""Shared catalog helpers (CSV validation, version hash, SQLite DDL/loader).

Status: PROPOSED. Normalization (K-12), period semantics (K-01/K-18) and null symbols (K-16)
are still OPEN in docs/13_DECISION_LOG.md. Nothing here invents BPS data: it only validates,
hashes and loads files that the data owner provides.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KATALOG_DIR = ROOT / "data" / "katalog"

HEADERS = {
    "indikator.csv": ["kode", "nama_kanonik", "definisi_resmi", "satuan", "sumber",
                      "cakupan_wilayah", "periode_tersedia"],
    "kamus_istilah.csv": ["istilah", "jenis", "kode"],
    "operasi.csv": ["kata", "operasi"],
    "provinsi.csv": ["kode", "nama"],
}
VERSIONED_FILES = ["indikator.csv", "kamus_istilah.csv", "operasi.csv", "provinsi.csv"]
VALID_OPERATIONS = {"NONE", "SUM", "AVG", "RANK"}
VALID_JENIS = {"indikator", "wilayah"}
PLACEHOLDER_RE = re.compile(r"^\s*(TODO|TBD|\[VERIFIKASI\]|XXX)", re.IGNORECASE)

# D04 section 3 DDL (PROPOSED, four tables from paper Table A-1).
DDL = """
PRAGMA foreign_keys = ON;
CREATE TABLE provinsi (
    kode TEXT NOT NULL PRIMARY KEY CHECK (length(trim(kode)) > 0),
    nama TEXT NOT NULL CHECK (length(trim(nama)) > 0)
);
CREATE TABLE indikator (
    kode TEXT NOT NULL PRIMARY KEY CHECK (length(trim(kode)) > 0),
    nama_kanonik TEXT NOT NULL CHECK (length(trim(nama_kanonik)) > 0),
    definisi_resmi TEXT NOT NULL CHECK (length(trim(definisi_resmi)) > 0),
    satuan TEXT NOT NULL CHECK (length(trim(satuan)) > 0),
    sumber TEXT NOT NULL CHECK (length(trim(sumber)) > 0),
    cakupan_wilayah TEXT NOT NULL CHECK (length(trim(cakupan_wilayah)) > 0),
    periode_tersedia TEXT NOT NULL CHECK (length(trim(periode_tersedia)) > 0)
);
CREATE TABLE nilai_indikator (
    kode_provinsi TEXT NOT NULL,
    kode_indikator TEXT NOT NULL,
    periode TEXT NOT NULL CHECK (length(trim(periode)) > 0),
    nilai REAL,
    PRIMARY KEY (kode_provinsi, kode_indikator, periode),
    FOREIGN KEY (kode_provinsi) REFERENCES provinsi(kode) ON DELETE RESTRICT,
    FOREIGN KEY (kode_indikator) REFERENCES indikator(kode) ON DELETE RESTRICT,
    CHECK (nilai IS NULL OR typeof(nilai) IN ('integer', 'real'))
);
CREATE TABLE kamus_istilah (
    istilah TEXT NOT NULL CHECK (length(trim(istilah)) > 0),
    jenis TEXT NOT NULL CHECK (jenis IN ('indikator', 'wilayah')),
    kode TEXT NOT NULL CHECK (length(trim(kode)) > 0),
    PRIMARY KEY (istilah, jenis, kode)
);
CREATE INDEX idx_nilai_indikator_lookup
    ON nilai_indikator (kode_indikator, periode, kode_provinsi);
"""


def normalize_term(text: str) -> str:
    """PROPOSED normalization (K-12 OPEN): NFKC, casefold, drop punctuation, collapse spaces."""
    t = unicodedata.normalize("NFKC", text).casefold()
    t = re.sub(r"[^\w\s%]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def read_csv(path: Path, expected_header: list[str] | None = None) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if expected_header is not None and reader.fieldnames != expected_header:
            raise ValueError(f"{path.name}: header {reader.fieldnames} != {expected_header}")
        return [dict(r) for r in reader]


def _parse_json_list(value: str) -> list[str] | None:
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return None
    if isinstance(parsed, list) and parsed and all(isinstance(x, str) and x for x in parsed):
        return parsed
    return None


def validate_catalog(katalog_dir: Path = KATALOG_DIR, allow_placeholders: bool = False) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors block a final snapshot; warnings need human review.

    allow_placeholders=True (draft ETL only) downgrades "masih placeholder" errors to warnings.
    """
    errors: list[str] = []
    warnings: list[str] = []
    tables: dict[str, list[dict]] = {}
    for name, header in HEADERS.items():
        p = katalog_dir / name
        if not p.exists():
            errors.append(f"{name}: berkas tidak ada")
            continue
        try:
            tables[name] = read_csv(p, header)
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        return errors, warnings

    def _placeholder(msg: str) -> None:
        (warnings if allow_placeholders else errors).append(msg)

    # provinsi.csv
    prov_codes: set[str] = set()
    for i, r in enumerate(tables["provinsi.csv"], start=2):
        kode, nama = (r["kode"] or "").strip(), (r["nama"] or "").strip()
        if not kode or not nama:
            errors.append(f"provinsi.csv baris {i}: kode/nama kosong")
        elif kode in prov_codes:
            errors.append(f"provinsi.csv baris {i}: kode ganda {kode}")
        prov_codes.add(kode)
    if not tables["provinsi.csv"]:
        errors.append("provinsi.csv: kosong")

    # indikator.csv
    ind_codes: set[str] = set()
    ind_rows = tables["indikator.csv"]
    if not ind_rows:
        errors.append("indikator.csv: belum ada baris indikator")
    for i, r in enumerate(ind_rows, start=2):
        kode = (r["kode"] or "").strip()
        if not kode:
            errors.append(f"indikator.csv baris {i}: kode kosong")
            continue
        if kode in ind_codes:
            errors.append(f"indikator.csv baris {i}: kode ganda {kode}")
        ind_codes.add(kode)
        for col in HEADERS["indikator.csv"][1:]:
            val = (r[col] or "").strip()
            if not val:
                errors.append(f"indikator.csv {kode}: kolom {col} kosong")
            elif PLACEHOLDER_RE.match(val):
                _placeholder(f"indikator.csv {kode}: kolom {col} masih placeholder ({val[:40]!r})")
        cov = _parse_json_list(r["cakupan_wilayah"] or "")
        per = _parse_json_list(r["periode_tersedia"] or "")
        if (r["cakupan_wilayah"] or "").strip() and not PLACEHOLDER_RE.match(r["cakupan_wilayah"]):
            if cov is None:
                errors.append(f"indikator.csv {kode}: cakupan_wilayah bukan array JSON string")
            else:
                unknown = [c for c in cov if c not in prov_codes]
                if unknown:
                    errors.append(f"indikator.csv {kode}: cakupan_wilayah berisi kode tak dikenal {unknown}")
        if (r["periode_tersedia"] or "").strip() and not PLACEHOLDER_RE.match(r["periode_tersedia"]):
            if per is None:
                errors.append(f"indikator.csv {kode}: periode_tersedia bukan array JSON string")

    # kamus_istilah.csv
    seen: set[tuple[str, str, str]] = set()
    seen_norm: set[tuple[str, str, str]] = set()
    seen_norm_raw: set[tuple[str, str, str]] = set()
    norm_map: dict[tuple[str, str], set[str]] = {}
    for i, r in enumerate(tables["kamus_istilah.csv"], start=2):
        istilah, jenis, kode = (r["istilah"] or "").strip(), (r["jenis"] or "").strip(), (r["kode"] or "").strip()
        if not istilah or not kode:
            errors.append(f"kamus_istilah.csv baris {i}: istilah/kode kosong")
            continue
        if jenis not in VALID_JENIS:
            errors.append(f"kamus_istilah.csv baris {i}: jenis {jenis!r} tidak sah")
            continue
        target = ind_codes if jenis == "indikator" else prov_codes
        if kode not in target:
            errors.append(f"kamus_istilah.csv baris {i}: kode {kode!r} tidak ada pada tabel {jenis}")
        key = (istilah, jenis, kode)
        if key in seen:
            errors.append(f"kamus_istilah.csv baris {i}: baris identik ganda {key}")
        seen.add(key)
        nkey = (normalize_term(istilah), jenis, kode)
        if nkey in seen_norm and key not in seen_norm_raw:
            errors.append(f"kamus_istilah.csv baris {i}: {istilah!r} bentrok setelah normalisasi dengan baris lain")
        seen_norm.add(nkey)
        seen_norm_raw.add(key)
        norm_map.setdefault((normalize_term(istilah), jenis), set()).add(kode)
        if normalize_term(istilah) != istilah:
            warnings.append(f"kamus_istilah.csv baris {i}: istilah {istilah!r} belum dalam bentuk ternormalisasi "
                            f"({normalize_term(istilah)!r}); exact match memakai bentuk ternormalisasi")
    covered = {k for (_, j), ks in norm_map.items() if j == "indikator" for k in ks}
    for k in sorted(ind_codes - covered):
        warnings.append(f"indikator {k} belum punya istilah di kamus_istilah.csv (tidak bisa ditemukan sistem)")
    if not tables["kamus_istilah.csv"]:
        errors.append("kamus_istilah.csv: belum ada baris")

    # operasi.csv
    for i, r in enumerate(tables["operasi.csv"], start=2):
        if (r["operasi"] or "").strip() not in VALID_OPERATIONS:
            errors.append(f"operasi.csv baris {i}: operasi {r['operasi']!r} tidak sah")
        if not (r["kata"] or "").strip():
            errors.append(f"operasi.csv baris {i}: kata kosong")
    return errors, warnings


def compute_version(katalog_dir: Path = KATALOG_DIR) -> dict:
    """Digest over (name, sha256-of-bytes) of the versioned files, sorted by name (PROPOSED, K-19)."""
    files = {}
    for name in sorted(VERSIONED_FILES):
        p = katalog_dir / name
        files[name] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    payload = json.dumps(files, sort_keys=True).encode()
    return {"algorithm": "sha256", "files": files, "catalog_hash": hashlib.sha256(payload).hexdigest()}


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)


def load_catalog(conn: sqlite3.Connection, katalog_dir: Path = KATALOG_DIR) -> dict:
    """Insert provinsi, indikator and kamus_istilah. Requires a clean schema (see create_schema)."""
    conn.execute("PRAGMA foreign_keys = ON")
    counts = {}
    for table, fname, cols in [
        ("provinsi", "provinsi.csv", HEADERS["provinsi.csv"]),
        ("indikator", "indikator.csv", HEADERS["indikator.csv"]),
        ("kamus_istilah", "kamus_istilah.csv", HEADERS["kamus_istilah.csv"]),
    ]:
        rows = read_csv(katalog_dir / fname, cols)
        if table == "kamus_istilah":
            for r in rows:
                r["istilah"] = normalize_term(r["istilah"])
        conn.executemany(
            f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            [tuple((r[c] or "").strip() for c in cols) for r in rows],
        )
        counts[table] = len(rows)
    return counts


_PAREN_RE = re.compile(r"\(([^)]*)\)")
_ABBR_RE = re.compile(r"^[A-Z]{2,6}$")
_DEF_ABBR_RE = re.compile(r"^\s*([A-Z]{2,6})\s*\(")
_RANGE_RE = re.compile(r"\d+\s*-\s*\d+")


def mechanical_indicator_terms(row: dict) -> list[str]:
    """Istilah turunan MEKANIS dari satu baris indikator (bukan sinonim awam).

    Sumber hanya nama_kanonik dan definisi_resmi pada indikator.csv:
      - nama penuh, dan nama tanpa tanda kurung ("angka partisipasi murni sma")
      - nama dasar tanpa kurung dan tanpa sufiks jenjang/umur ("angka partisipasi murni")
      - singkatan resmi: dalam kurung pada nama ("(APM)") atau pembuka definisi ("TPT (Tingkat ...")
      - singkatan + sufiks ("apm sma", "aps 7-12"). Tidak ada sinonim yang dikarang di sini.
    """
    nama = (row["nama_kanonik"] or "").strip()
    terms = [nama]
    parens = _PAREN_RE.findall(nama)
    abbr = next((x.strip() for x in parens if _ABBR_RE.match(x.strip())), None)
    if abbr is None:
        m = _DEF_ABBR_RE.match(row.get("definisi_resmi") or "")
        abbr = m.group(1) if m else None
    if parens:
        before, _, after = nama.partition("(")
        suffix = after.partition(")")[2].strip()
        base = before.strip()
        terms.append(f"{base} {suffix}".strip())          # tanpa kurung, dengan sufiks
        if suffix:
            terms.append(base)                              # nama dasar (1:N ke semua jenjang/umur)
        if abbr and suffix:
            terms.append(f"{abbr} {suffix}")
            rng = _RANGE_RE.search(suffix)
            if rng:
                terms.append(f"{abbr} {rng.group(0)}")
    if abbr:
        terms.append(abbr)
    return terms
