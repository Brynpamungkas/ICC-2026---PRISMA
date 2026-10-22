"""Column names/types from the existing D04/ETL schema, without data rows.

This is validation/prompt metadata, not a new database or schema migration.
The regression suite checks it against scripts.catalog_lib.create_schema.
"""

SQL_SCHEMA: dict[str, dict[str, str]] = {
    "provinsi": {"kode": "TEXT", "nama": "TEXT"},
    "indikator": {
        "kode": "TEXT", "nama_kanonik": "TEXT", "definisi_resmi": "TEXT",
        "satuan": "TEXT", "sumber": "TEXT", "cakupan_wilayah": "TEXT",
        "periode_tersedia": "TEXT",
    },
    "nilai_indikator": {
        "kode_provinsi": "TEXT", "kode_indikator": "TEXT", "periode": "TEXT", "nilai": "REAL",
    },
    "kamus_istilah": {"istilah": "TEXT", "jenis": "TEXT", "kode": "TEXT"},
}
