# Tes batas paket rilis

Memeriksa integritas source/bukti, aset frontend yang diimpor, profil asal dan penolakan penggunaan ulang build yang tidak cocok.

## Penggunaan dan batas

Dari root: `.venv/bin/python -B -m pytest release/tests -q -p no:cacheprovider`. Tes ini melindungi packaging; tidak menggantikan golden, tes API, eksperimen atau demo model nyata.

## Berkas yang tersedia

- `test_release_cli.py`

[Panduan utama](../../README.md) · [Evaluasi dan reproduksibilitas](../../EVALUATION.md)
