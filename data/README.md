# Snapshot data BPS

Database `prisma.sqlite`, katalog dan bahan mentah BPS yang mendasarinya. SQLite disertakan agar aplikasi membaca snapshot yang sama dengan manifest penelitian.

## Penggunaan dan batas

Aplikasi memakai SQLite mode read-only. Asal data berada di `raw_bps/`; metadata/istilah ada di `katalog/`. Jangan mengedit angka atau menjalankan ETL menimpa snapshot rilis tanpa proses pembaruan data yang diotorisasi.

## Subfolder

- [katalog](katalog/README.md)
- [raw_bps](raw_bps/README.md)

## Berkas yang tersedia

- `etl_report.json`
- `prisma.sqlite`

[Panduan utama](../README.md) · [Evaluasi dan reproduksibilitas](../EVALUATION.md)
