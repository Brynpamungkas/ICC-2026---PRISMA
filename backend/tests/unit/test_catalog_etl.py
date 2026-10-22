"""Tes unit katalog + ETL. Semua data = SYNTHETIC (bukan data BPS)."""
import csv
import json
import sqlite3
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import build_catalog  # noqa: E402
import catalog_lib as cl  # noqa: E402
import etl  # noqa: E402


def write_csv(path: Path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


@pytest.fixture
def env(tmp_path, monkeypatch):
    kat, raw = tmp_path / "katalog", tmp_path / "raw"
    kat.mkdir()
    raw.mkdir()
    write_csv(kat / "provinsi.csv", ["kode", "nama"], [["01", "Provinsi Alfa"], ["02", "Provinsi Beta"], ["03", "Provinsi Gamma"]])
    write_csv(kat / "indikator.csv", cl.HEADERS["indikator.csv"], [
        ["SYN_PERSEN", "Persentase Contoh (SYNTHETIC)", "def sintetis", "%", "SYNTHETIC", json.dumps(["01", "02", "03"]), json.dumps(["2025-03", "2025-09"])],
        ["SYN_JUMLAH", "Jumlah Contoh (SYNTHETIC)", "def sintetis", "ribu jiwa", "SYNTHETIC", json.dumps(["01", "02", "03"]), json.dumps(["2025-03"])],
    ])
    write_csv(kat / "kamus_istilah.csv", cl.HEADERS["kamus_istilah.csv"], [
        ["contoh", "indikator", "SYN_PERSEN"], ["contoh", "indikator", "SYN_JUMLAH"],
        ["Provinsi Alfa", "wilayah", "01"], ["wilayah x", "wilayah", "01"], ["wilayah x", "wilayah", "02"],
    ])
    write_csv(kat / "operasi.csv", cl.HEADERS["operasi.csv"], [["total", "SUM"], ["rata-rata", "AVG"]])
    grid = [["Tabel sintetis", "", "", ""],
            ["Provinsi", "Persentase", "", "Jumlah"],
            ["", "Maret 2025", "September 2025", "Maret 2025"],
            ["PROVINSI ALFA", "9,50", "9,10", "1.234,5"],
            ["Beta", "-", "5,00", "800,0"],
            ["Gamma", "7,25", "7,00", "300,5"],
            ["INDONESIA", "8,00", "8,00", "2.000,0"],
            ["Sumber: sintetis", "", "", ""]]
    write_csv(raw / "syn.csv", ["a", "b", "c", "d"], grid)  # baris header csv ikut jadi baris 0
    manifest = {
        "null_symbols": ["-"], "decimal": ",", "skip_names": ["INDONESIA"],
        "sources": [{"file": "syn.csv", "format": "wide", "header_rows": [2, 3], "province_col": 0, "columns": [
            {"col": 1, "kode_indikator": "SYN_PERSEN", "periode": "2025-03"},
            {"col": 2, "kode_indikator": "SYN_PERSEN", "periode": "2025-09"},
            {"col": 3, "kode_indikator": "SYN_JUMLAH", "periode": "2025-03"}]}],
    }
    (raw / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    monkeypatch.setattr(etl, "RAW_DIR", raw)
    monkeypatch.setattr(etl, "KATALOG_DIR", kat)
    return kat, raw, tmp_path


def test_validate_ok(env):
    kat, _, _ = env
    errors, _ = cl.validate_catalog(kat)
    assert errors == []


def test_validate_rejects_bad_targets_and_placeholders(env):
    kat, _, _ = env
    write_csv(kat / "kamus_istilah.csv", cl.HEADERS["kamus_istilah.csv"], [["x", "indikator", "TIDAK_ADA"], ["y", "wilayah", "99"], ["z", "lainnya", "01"]])
    errors, _ = cl.validate_catalog(kat)
    assert len(errors) == 3
    rows = cl.read_csv(kat / "indikator.csv", cl.HEADERS["indikator.csv"])
    rows[0]["definisi_resmi"] = "TODO: salin dari Sirusa"
    write_csv(kat / "indikator.csv", cl.HEADERS["indikator.csv"], [[r[c] for c in cl.HEADERS["indikator.csv"]] for r in rows])
    errors, _ = cl.validate_catalog(kat)
    assert any("placeholder" in e for e in errors)
    errors, warnings = cl.validate_catalog(kat, allow_placeholders=True)
    assert not any("placeholder" in e for e in errors) and any("placeholder" in w for w in warnings)


def test_one_to_many_alias_allowed(env):
    kat, _, _ = env
    errors, _ = cl.validate_catalog(kat)
    assert errors == []  # 'contoh' -> 2 indikator dan 'wilayah x' -> 2 provinsi sah


def test_version_changes_with_content(env):
    kat, _, _ = env
    v1 = cl.compute_version(kat)["catalog_hash"]
    (kat / "operasi.csv").write_text("kata,operasi\ntotal,SUM\n", encoding="utf-8")
    assert cl.compute_version(kat)["catalog_hash"] != v1


def test_etl_builds_and_is_idempotent(env):
    _, _, tmp = env
    out, rep = tmp / "p.sqlite", tmp / "r.json"
    assert etl.build(False, etl.RAW_DIR / "manifest.yaml", out, rep) == 0
    h1 = json.loads(rep.read_text())["logical_hash"]
    conn = sqlite3.connect(out)
    rows = conn.execute("SELECT kode_provinsi,kode_indikator,periode,nilai FROM nilai_indikator ORDER BY 1,2,3").fetchall()
    conn.close()
    assert len(rows) == 9
    assert ("01", "SYN_JUMLAH", "2025-03", 1234.5) in rows
    assert ("02", "SYN_PERSEN", "2025-03", None) in rows  # '-' -> NULL, bukan 0
    assert etl.build(False, etl.RAW_DIR / "manifest.yaml", out, rep) == 0
    assert json.loads(rep.read_text())["logical_hash"] == h1


def test_etl_fails_on_unknown_province_and_keeps_old_db(env):
    _, raw, tmp = env
    out, rep = tmp / "p.sqlite", tmp / "r.json"
    assert etl.build(False, raw / "manifest.yaml", out, rep) == 0
    before = out.read_bytes()
    text = (raw / "syn.csv").read_text().replace("Gamma", "Provinsi Tak Dikenal")
    (raw / "syn.csv").write_text(text)
    assert etl.build(False, raw / "manifest.yaml", out, rep) == 1
    assert out.read_bytes() == before
    assert any("tidak dikenal" in e for e in json.loads(rep.read_text())["errors"])


def test_etl_fails_on_non_numeric_without_null_symbol(env):
    _, raw, tmp = env
    m = yaml.safe_load((raw / "manifest.yaml").read_text())
    m["null_symbols"] = []
    (raw / "manifest.yaml").write_text(yaml.safe_dump(m))
    assert etl.build(False, raw / "manifest.yaml", tmp / "p.sqlite", tmp / "r.json") == 1


def test_etl_fails_on_duplicate_pk(env):
    _, raw, tmp = env
    m = yaml.safe_load((raw / "manifest.yaml").read_text())
    m["sources"].append(dict(m["sources"][0]))
    (raw / "manifest.yaml").write_text(yaml.safe_dump(m))
    assert etl.build(False, raw / "manifest.yaml", tmp / "p.sqlite", tmp / "r.json") == 1


def test_build_catalog_load_db_and_version(env, tmp_path):
    kat, _, _ = env
    assert build_catalog.main(["--katalog-dir", str(kat), "--version"]) == 0
    assert (kat / "VERSION").exists()
    db = tmp_path / "c.sqlite"
    assert build_catalog.main(["--katalog-dir", str(kat), "--load-db", str(db)]) == 0
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT count(*) FROM kamus_istilah").fetchone()[0] == 5
    conn.close()


def test_ddl_enforces_constraints():
    conn = sqlite3.connect(":memory:")
    cl.create_schema(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO nilai_indikator VALUES ('x','y','2025-03',1.0)")


def test_mechanical_terms_from_official_names():
    apm = {"nama_kanonik": "Angka Partisipasi Murni (APM) SMA", "definisi_resmi": "x"}
    aps = {"nama_kanonik": "Angka Partisipasi Sekolah (APS) Umur 7-12 Tahun", "definisi_resmi": "x"}
    tpt = {"nama_kanonik": "Tingkat Pengangguran Terbuka",
           "definisi_resmi": "TPT (Tingkat Pengangguran Terbuka) adalah persentase ..."}
    miskin = {"nama_kanonik": "Persentase Penduduk Miskin", "definisi_resmi": "Proporsi penduduk ..."}
    n = lambda row: {cl.normalize_term(t) for t in cl.mechanical_indicator_terms(row)}  # noqa: E731
    assert {"apm", "apm sma", "angka partisipasi murni sma", "angka partisipasi murni"} <= n(apm)
    assert {"aps", "aps 7 12", "angka partisipasi sekolah"} <= n(aps)
    assert "tpt" in n(tpt)
    assert n(miskin) == {"persentase penduduk miskin"}   # tidak ada singkatan karangan (mis. "ppm")


def test_seed_kamus_adds_variants_idempotently(env):
    kat, _, _ = env
    rows = cl.read_csv(kat / "indikator.csv", cl.HEADERS["indikator.csv"])
    rows[0]["nama_kanonik"] = "Angka Partisipasi Murni (APM) SMA"
    write_csv(kat / "indikator.csv", cl.HEADERS["indikator.csv"], [[r[c] for c in cl.HEADERS["indikator.csv"]] for r in rows])
    assert build_catalog.main(["--katalog-dir", str(kat), "--seed-kamus"]) == 0
    first = (kat / "kamus_istilah.csv").read_text(encoding="utf-8")
    assert "apm sma,indikator,SYN_PERSEN" in first and "angka partisipasi murni sma,indikator,SYN_PERSEN" in first
    assert build_catalog.main(["--katalog-dir", str(kat), "--seed-kamus"]) == 0
    assert (kat / "kamus_istilah.csv").read_text(encoding="utf-8") == first
    errors, _ = cl.validate_catalog(kat)
    assert errors == []