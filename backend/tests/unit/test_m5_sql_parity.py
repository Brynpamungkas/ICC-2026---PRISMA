"""SYNTHETIC regressions adapted from integrasi/m5@314076f.

Keep the CPU guard's schema/CTE checks while adding the shared binding and
operation-shape checks. No model calls or research data are used here.
"""
import pytest

from backend.app.sqlguard.validator import validate_sql


BASE = (
    "SELECT p.nama AS wilayah, n.nilai AS nilai FROM nilai_indikator n "
    "JOIN provinsi p ON p.kode=n.kode_provinsi "
    "WHERE n.kode_indikator=:indikator AND n.periode=:periode"
)


@pytest.mark.parametrize("condition,expected", [
    ("n.kode_provinsi IN (:wilayah_0, :wilayah_1)", True),
    ("p.kode IN (:wilayah_0, :wilayah_1)", True),
    (":wilayah_0=n.kode_provinsi AND n.kode_provinsi=:wilayah_1", True),
    ("p.nama IN (:wilayah_0, :wilayah_1)", False),
    ("p.nama=:wilayah_0 AND n.kode_provinsi=:wilayah_1", False),
    ("n.kode_provinsi>:wilayah_0 AND n.kode_provinsi<:wilayah_1", False),
])
def test_region_bindings_target_codes(condition, expected):
    assert validate_sql(BASE + " AND " + condition, region_count=2)[0] is expected


@pytest.mark.parametrize("suffix,shape,expected", [
    ("", ("NONE", None, 1), True),
    (" LIMIT 1", ("NONE", None, 1), False),
    (" GROUP BY p.nama", ("NONE", None, 1), False),
    (" ORDER BY nilai DESC LIMIT 3", ("RANK", "highest", 3), True),
    (" ORDER BY nilai ASC LIMIT 3", ("RANK", "lowest", 3), True),
    (" ORDER BY nilai DESC LIMIT 3", ("RANK", "lowest", 3), False),
    (" ORDER BY nilai DESC LIMIT 1", ("RANK", "highest", 3), False),
    (" ORDER BY nilai DESC", ("RANK", "highest", 3), False),
])
def test_lookup_and_ranking_shape(suffix, shape, expected):
    assert validate_sql(BASE + suffix, shape=shape)[0] is expected


@pytest.mark.parametrize("operation,query,expected", [
    ("SUM", "SELECT SUM(n.nilai) AS nilai", True),
    ("AVG", "SELECT AVG(n.nilai) AS nilai", True),
    ("SUM", "SELECT AVG(n.nilai) AS nilai", False),
    ("AVG", "SELECT SUM(n.nilai) AS nilai", False),
    ("NONE", "SELECT SUM(n.nilai) AS nilai", False),
    ("SUM", "SELECT p.nama AS wilayah, SUM(n.nilai) AS nilai", False),
])
def test_aggregate_shape(operation, query, expected):
    sql = query + BASE[BASE.index(" FROM "):]
    assert validate_sql(sql, shape=(operation, None, 1))[0] is expected


def test_optional_shape_does_not_remove_schema_or_cte_checks():
    sql = "WITH c AS (SELECT nilai FROM nilai_indikator WHERE kode_indikator=:indikator) SELECT nilai FROM c"
    assert validate_sql(sql)[0]
    assert not validate_sql(BASE.replace("n.nilai AS nilai", "p.nilai AS nilai"))[0]
    assert not validate_sql(BASE.replace("FROM nilai_indikator n", "FROM other.nilai_indikator n"))[0]
