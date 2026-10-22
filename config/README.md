# Konfigurasi runtime dan evaluasi

Konfigurasi sumber berisi identitas model, sampling, SQL, katalog, aturan keputusan, transport/API dan frontend. Nilai tau dipisahkan pada berkas tau yang tersedia.

## Penggunaan dan batas

Profil aktif dipilih launcher melalui `release/profile.json`. Semua konfigurasi sumber dilindungi checksum. Perubahan riset memerlukan versi/bukti baru; jangan mengubah tau, prompt atau label berdasarkan hasil test yang sudah dibuka.

Profil folder ini: **CPU llama.cpp/GGUF N8**, konfigurasi aktif `config/cpu.eval.yaml`.

## Berkas yang tersedia

- `config.yaml`
- `cpu.eval.yaml`
- `local.cpu.yaml`
- `tau_u.cpu.yaml`
- `tau_u.yaml`

[Panduan utama](../README.md) · [Evaluasi dan reproduksibilitas](../EVALUATION.md)
