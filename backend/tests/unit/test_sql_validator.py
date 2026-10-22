"""Schema regression checks; SYNTHETIC queries, never research labels."""
import sqlite3

import pytest

from backend.app.sqlguard.validator import validate_sql
from scripts.catalog_lib import create_schema


@pytest.mark.parametrize("sql", [
    "SELECT i.periode AS periode FROM indikator i WHERE i.kode=:indikator",
    "SELECT n.unknown_column AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:indikator",
    "SELECT x.nilai AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:indikator",
    "SELECT n.nilai AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:indikator AND n.unknown_column=1",
    "SELECT n.nilai AS nilai FROM nilai_indikator n JOIN provinsi p ON p.unknown_column=n.kode_provinsi WHERE n.kode_indikator=:indikator",
    "SELECT kode AS nilai FROM indikator i JOIN provinsi p ON i.kode=p.kode WHERE i.kode=:indikator",
    "SELECT n.nilai AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:indikator ORDER BY n.unknown_column",
    "WITH c AS (SELECT unknown_column AS nilai FROM nilai_indikator WHERE kode_indikator=:indikator) SELECT nilai FROM c",
    "SELECT n.nilai AS nilai FROM external.nilai_indikator n WHERE n.kode_indikator=:indikator",
])
def test_unknown_ambiguous_or_foreign_columns_are_rejected(sql):
    ok, reason = validate_sql(sql)
    assert not ok and reason


@pytest.mark.parametrize("sql", [
    "SELECT p.nama AS wilayah,n.nilai AS nilai FROM nilai_indikator n JOIN provinsi p ON p.kode=n.kode_provinsi WHERE n.kode_indikator=:indikator AND n.periode=:periode ORDER BY nilai DESC LIMIT 1",
    "SELECT SUM(nilai) AS nilai FROM nilai_indikator WHERE kode_indikator=:indikator",
    "SELECT n.periode AS periode,n.nilai AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:indikator ORDER BY periode",
    "SELECT n.nilai AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:indikator AND n.nilai > (SELECT AVG(m.nilai) FROM nilai_indikator m WHERE m.kode_indikator=n.kode_indikator)",
    "WITH c AS (SELECT nilai FROM nilai_indikator WHERE kode_indikator=:indikator) SELECT nilai FROM c",
])
def test_existing_valid_aliases_ctes_and_correlated_queries_still_pass(sql):
    assert validate_sql(sql) == (True, None)


def test_validation_schema_matches_existing_etl_ddl():
    from backend.app.sqlguard.schema import SQL_SCHEMA

    connection = sqlite3.connect(":memory:")
    try:
        create_schema(connection)
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert set(SQL_SCHEMA) == tables
        for table, columns in SQL_SCHEMA.items():
            actual = {row[1]: row[2] for row in connection.execute(f'PRAGMA table_info("{table}")')}
            assert columns == actual
    finally:
        connection.close()
