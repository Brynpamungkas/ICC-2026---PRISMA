# Evaluasi penelitian

`annotations/` memuat corpus/label/rujukan; `testset/` memuat split. Hasil penelitian historis dipindahkan ke `evidence/`; output baru masuk `eval/runs/` yang diabaikan Git.

## Penggunaan dan batas

Penghitungan ulang tanpa model: `.venv/bin/python -B tools/release_cli.py replay` dari root. Ini menghitung metrik dari record tersimpan, bukan inferensi ulang atau replay seluruh sampel. Lihat panduan evaluasi root sebelum menjalankan eksperimen baru.

## Subfolder

- [annotations](annotations/README.md)
- [testset](testset/README.md)

[Panduan utama](../README.md) · [Evaluasi dan reproduksibilitas](../EVALUATION.md)
