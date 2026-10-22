"""Keputusan tim 20 Okt 2026: K-03 (tanpa literal teks; parameter wilayah sesuai ekstraksi) dan K-16 (hasil hanya NULL =
tanpa nilai -> T5). Data SYNTHETIC; DB pipeline memakai hasil ETL data BPS asli seperti test_pipeline_mock."""
import sys
from pathlib import Path

import pytest

from backend.app.orchestrator import no_value
from backend.app.schemas import ExecResult
from backend.app.sqlguard.validator import validate_sql

ROOT = Path(__file__).resolve().parents[3]
BASE = "SELECT SUM(n.nilai) AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:indikator AND n.periode=:periode"


def _r(columns, rows, error=None):
    return ExecResult(candidate_code="X", columns=columns, rows=rows, structure="NUMBER", unit="%", error=error)


@pytest.mark.parametrize("sql,regions,ok", [
    (BASE + " AND n.kode_provinsi IN (:wilayah_0,:wilayah_1)", 2, True),
    (BASE + " AND n.kode_provinsi IN (:wilayah_0)", 2, False),                       # kurang dari ekstraksi
    (BASE + " AND n.kode_provinsi IN (:wilayah_0,:wilayah_1)", 0, False),            # wilayah padahal tidak ada
    (BASE, 0, True),
    (BASE + " AND n.kode_provinsi = '11'", 0, False),                                # literal teks
    ("SELECT n.nilai AS nilai FROM nilai_indikator n JOIN provinsi p ON p.kode=n.kode_provinsi "
     "WHERE n.kode_indikator=:indikator AND p.nama='Aceh'", None, False),
])
def test_k03_literals_and_region_params(sql, regions, ok):
    assert validate_sql(sql, region_count=regions)[0] is ok


def test_k03_numeric_literals_still_allowed():
    assert validate_sql(BASE + " AND n.nilai > 0")[0]


@pytest.mark.parametrize("res,expected", [
    (_r(["nilai"], []), True),
    (_r(["nilai"], [[None]]), True),                                     # AVG atas nol baris
    (_r(["wilayah", "nilai"], [["A", None], ["B", None]]), True),
    (_r(["wilayah", "nilai"], [["A", None], ["B", 1.0]]), False),        # NULL parsial tetap bernilai
    (_r(["wilayah"], [["A"]]), False),                                   # hanya kolom teks: barisnya adalah nilai
    (_r(["nilai"], [[0.0]]), False),
])
def test_k16_no_value(res, expected):
    assert no_value(res) is expected


def test_k16_avg_over_no_rows_is_t5_not_jawab(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import etl
    from backend.app.llm.mock import MockLlmClient
    from backend.app.orchestrator import run_question_with_log
    db = tmp_path / "p.sqlite"
    assert etl.build(False, etl.RAW_DIR / "manifest.yaml", db, tmp_path / "r.json") == 0
    sql = ("SELECT AVG(n.nilai) AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:indikator "
           "AND n.periode=:periode AND n.kode_provinsi IN (:wilayah_0,:wilayah_1,:wilayah_2,:wilayah_3,:wilayah_4,:wilayah_5) "
           "AND n.nilai > 1e12")
    d, rec = run_question_with_log("Rata-rata tingkat pengangguran terbuka di pulau jawa?", llm=MockLlmClient([sql]),
                                   db_path=db, tau={"%": 0.0})
    assert d.decision == "TAHAN" and d.reason_code == "T5"
