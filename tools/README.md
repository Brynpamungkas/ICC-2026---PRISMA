# Alat penyiapan rilis

`release_cli.py` menyediakan setup, run, verify dan replay untuk paket rilis. Kode algoritma penelitian tetap berada di backend tanpa disatukan antarprofil.

## Penggunaan dan batas

Setup memasang dependensi/model sesuai profil bila diperlukan; run memulai layanan dan hanya menghentikan prosesnya sendiri. Verify mencocokkan hash. Replay menghitung ulang metrik dari record historis, tanpa model. --reuse-build memakai build lama secara eksplisit setelah pemeriksaan source/proxy; bukan bukti build baru.

Profil folder ini: **CPU llama.cpp/GGUF N8**, konfigurasi aktif `config/cpu.eval.yaml`.

## Berkas yang tersedia

- `release_cli.py`

[Panduan utama](../README.md) · [Evaluasi dan reproduksibilitas](../EVALUATION.md)
