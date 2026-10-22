# Tes unit

Pengujian fungsi, kontrak dan aturan lokal berdasarkan snapshot profil ini. Daftar tes berbeda antara branch CPU dan GPU karena versi implementasinya berbeda.

## Penggunaan dan batas

Dari root: `PRISMA_CONFIG=config/config.yaml .venv/bin/python -B -m pytest backend/tests/unit -q -p no:cacheprovider`. Simpan hasil aktual; jumlah tes dan status tidak boleh diasumsikan sama dengan branch lain.

## Berkas yang tersedia

- `test_api_schemas.py`
- `test_catalog_etl.py`
- `test_dataset_tools.py`
- `test_eval_metrics.py`
- `test_m2_steps.py`
- `test_prompt_m3.py`
- `test_schemas.py`
- `test_team_decisions_k03_k16.py`

[Panduan utama](../../../README.md) · [Evaluasi dan reproduksibilitas](../../../EVALUATION.md)
