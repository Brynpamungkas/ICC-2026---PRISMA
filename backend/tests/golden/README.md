# Golden FROZEN

Kasus emas yang dilindungi pada snapshot sumber. Status tiga tes masih skipped, sebagaimana kode asalnya.

## Penggunaan dan batas

Jalankan dari root: `.venv/bin/python -B -m pytest backend/tests/golden -q -p no:cacheprovider`. Smoke tiga kasus melalui engine/HTTP merupakan bukti terpisah dan tidak otomatis meluluskan tes golden FROZEN atau G2/G3/G4.

## Berkas yang tersedia

- `test_golden.py`

[Panduan utama](../../../README.md) · [Evaluasi dan reproduksibilitas](../../../EVALUATION.md)
