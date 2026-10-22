"""Katalog PRISMA: validasi CSV, tulis data/katalog/VERSION (hash), muat katalog ke DB.

Pemakaian:
  python scripts/build_catalog.py --validate            # cek konsistensi (exit 1 bila ada error)
  python scripts/build_catalog.py --version             # tulis data/katalog/VERSION
  python scripts/build_catalog.py --load-db DB.sqlite   # muat provinsi/indikator/kamus ke DB baru
  python scripts/build_catalog.py --suggest-coverage    # usul cakupan_wilayah/periode_tersedia dari data/prisma.sqlite
  python scripts/build_catalog.py --seed-kamus          # tambah baris MEKANIS ke kamus (varian nama kanonik, singkatan resmi, nama provinsi, "pulau jawa")
Usulan --suggest-coverage hanya bantuan QA: periode teramati BUKAN otomatis definisi periode_tersedia
(K-01/K-18 OPEN); pemilik data menyalin dan menyetujui sendiri.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_lib as cl  # noqa: E402


def cmd_validate(katalog_dir: Path) -> int:
    errors, warnings = cl.validate_catalog(katalog_dir)
    for w in warnings:
        print(f"WARNING  {w}")
    for e in errors:
        print(f"ERROR    {e}")
    print(f"\n{len(errors)} error, {len(warnings)} warning")
    if errors:
        print("Katalog BELUM siap sebagai snapshot final.")
        return 1
    print("Katalog konsisten secara struktural (bukan bukti keabsahan isi terhadap sumber BPS).")
    return 0


def cmd_version(katalog_dir: Path) -> int:
    errors, _ = cl.validate_catalog(katalog_dir)
    if errors:
        print("Menolak menulis VERSION: katalog belum valid. Jalankan --validate.")
        return 1
    ver = cl.compute_version(katalog_dir)
    (katalog_dir / "VERSION").write_text(json.dumps(ver, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"VERSION ditulis: {ver['catalog_hash']}")
    return 0


def cmd_load_db(katalog_dir: Path, db_path: Path) -> int:
    errors, _ = cl.validate_catalog(katalog_dir)
    if errors:
        print("Menolak memuat: katalog belum valid. Jalankan --validate.")
        return 1
    if db_path.exists():
        print(f"{db_path} sudah ada; hapus dulu atau pakai scripts/etl.py yang membangun ulang dari nol.")
        return 1
    conn = sqlite3.connect(db_path)
    try:
        cl.create_schema(conn)
        counts = cl.load_catalog(conn, katalog_dir)
        conn.commit()
    finally:
        conn.close()
    print(json.dumps(counts))
    return 0


JAWA_PROVINCES = ["DKI Jakarta", "Jawa Barat", "Jawa Tengah", "DI Yogyakarta", "Jawa Timur", "Banten"]  # paper III-B: 6 provinsi


def cmd_seed_kamus(katalog_dir: Path) -> int:
    """Append mechanical rows only (idempotent). Hand-written aliases/synonyms are never generated here."""
    prov = cl.read_csv(katalog_dir / "provinsi.csv", cl.HEADERS["provinsi.csv"])
    ind = cl.read_csv(katalog_dir / "indikator.csv", cl.HEADERS["indikator.csv"])
    kam_path = katalog_dir / "kamus_istilah.csv"
    existing = cl.read_csv(kam_path, cl.HEADERS["kamus_istilah.csv"])
    have = {(cl.normalize_term(r["istilah"]), r["jenis"], r["kode"]) for r in existing}
    new: list[list[str]] = []

    def add(term: str, jenis: str, kode: str) -> None:
        key = (cl.normalize_term(term), jenis, kode)
        if key not in have:
            have.add(key)
            new.append([key[0], jenis, kode])

    for r in ind:
        for term in cl.mechanical_indicator_terms(r):
            add(term, "indikator", r["kode"].strip())
    by_name = {r["nama"].strip(): r["kode"].strip() for r in prov}
    for nama, kode in by_name.items():
        add(nama, "wilayah", kode)
    missing = [n for n in JAWA_PROVINCES if n not in by_name]
    if missing:
        print(f"Alias 'pulau jawa' dilewati: provinsi tidak ada di provinsi.csv: {missing}")
    else:
        for n in JAWA_PROVINCES:
            add("pulau jawa", "wilayah", by_name[n])
    with open(kam_path, "a", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(new)
    print(f"{len(new)} baris mekanis ditambahkan ke kamus_istilah.csv")
    return 0


def cmd_suggest(db_path: Path) -> int:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT kode_indikator, kode_provinsi, periode FROM nilai_indikator WHERE nilai IS NOT NULL"
    ).fetchall()
    conn.close()
    agg: dict[str, dict[str, set]] = {}
    for ind, prov, per in rows:
        a = agg.setdefault(ind, {"prov": set(), "per": set()})
        a["prov"].add(prov)
        a["per"].add(per)
    for ind in sorted(agg):
        print(f"# {ind}")
        print("cakupan_wilayah =", json.dumps(sorted(agg[ind]["prov"])))
        print("periode_tersedia =", json.dumps(sorted(agg[ind]["per"])))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--katalog-dir", type=Path, default=cl.KATALOG_DIR)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--validate", action="store_true")
    g.add_argument("--version", action="store_true")
    g.add_argument("--load-db", type=Path, metavar="DB")
    g.add_argument("--suggest-coverage", action="store_true")
    g.add_argument("--seed-kamus", action="store_true")
    ap.add_argument("--db", type=Path, default=cl.ROOT / "data" / "prisma.sqlite")
    a = ap.parse_args(argv)
    if a.validate:
        return cmd_validate(a.katalog_dir)
    if a.version:
        return cmd_version(a.katalog_dir)
    if a.load_db:
        return cmd_load_db(a.katalog_dir, a.load_db)
    if a.seed_kamus:
        return cmd_seed_kamus(a.katalog_dir)
    return cmd_suggest(a.db)


if __name__ == "__main__":
    sys.exit(main())
