# Validasi dan eksekusi SQL

Validator memeriksa SQL model sebelum eksekusi; executor membuka SQLite hanya-baca dan memberlakukan batas eksekusi.

## Penggunaan dan batas

SQL valid belum membuktikan interpretasi atau jawaban benar. Semua SQL model harus melalui validator dan executor; jangan melewati guard untuk membuat kasus tertentu lulus. Galat eksekusi berbeda dari hasil kosong.

## Berkas yang tersedia

- `executor.py`
- `schema.py`
- `validator.py`

[Panduan utama](../../../README.md) · [Evaluasi dan reproduksibilitas](../../../EVALUATION.md)
