# Snapshot dependensi sumber

Salinan berkas requirements asal untuk penelusuran. Snapshot historis tidak otomatis portabel ke semua OS, Python atau GPU.

## Penggunaan dan batas

Setup rilis memakai requirements-api.lock di root. Branch GPU memakai requirements-model.lock di environment model terpisah. Lihat README root untuk perbedaan snapshot API Linux, snapshot historis Windows dan model NVIDIA.

## Berkas yang tersedia

- `source-requirements-core.lock`
- `source-requirements-gpu.lock`
- `source-requirements-gpu.txt`
- `source-requirements.txt`

[Panduan utama](../../README.md) · [Evaluasi dan reproduksibilitas](../../EVALUATION.md)
