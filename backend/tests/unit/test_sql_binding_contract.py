"""Team K-03 binding contract on SYNTHETIC SQL; no new research labels."""
import pytest

from backend.app.sqlguard.validator import validate_sql

BASE = "SELECT n.nilai AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:indikator AND n.periode=:periode"


@pytest.mark.parametrize("suffix,count,expected", [
    ("", 0, True),
    ("", 1, False),
    (" AND n.kode_provinsi=:wilayah_0", 1, True),
    (" AND n.kode_provinsi=:wilayah_0", 2, False),
    (" AND n.kode_provinsi IN (:wilayah_0,:wilayah_1)", 2, True),
    (" AND n.kode_provinsi IN (:wilayah_0,:wilayah_1)", 1, False),
    (" AND n.kode_provinsi='P_SYN'", 0, False),
    (" AND n.periode='2099-01'", 0, False),
    (" AND n.nilai>1e12", 0, True),
])
def test_exact_region_bindings_and_no_text_literals(suffix, count, expected):
    assert validate_sql(BASE + suffix, region_count=count)[0] is expected
