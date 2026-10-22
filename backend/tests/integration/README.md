# Tes integrasi

Memeriksa hubungan API, pipeline mock dan kondisi pembanding K1/K2 sesuai berkas tes yang tersedia.

## Penggunaan dan batas

Dari root: `PRISMA_CONFIG=config/config.yaml .venv/bin/python -B -m pytest backend/tests/integration -q -p no:cacheprovider`. Pada pemeriksaan rilis sebelumnya, subset pipeline/K1/K2 selesai; full suite termasuk API tidak selesai pada shell AI. Jalankan ulang di terminal biasa untuk bukti lengkap.

## Berkas yang tersedia

- `test_api.py`
- `test_conditions_k1_k2.py`
- `test_pipeline_mock.py`

[Panduan utama](../../../README.md) · [Evaluasi dan reproduksibilitas](../../../EVALUATION.md)
