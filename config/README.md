# Konfigurasi runtime dan evaluasi

Konfigurasi sumber berisi identitas model, sampling, SQL, katalog, aturan keputusan, transport/API dan frontend. Nilai tau dipisahkan pada berkas tau yang tersedia.

## Penggunaan dan batas

Profil aktif dipilih launcher melalui `release/profile.json`. Semua konfigurasi sumber dilindungi checksum. Perubahan riset memerlukan versi/bukti baru; jangan mengubah tau, prompt atau label berdasarkan hasil test yang sudah dibuka.

Profil folder ini: **NVIDIA vLLM/AWQ N64**, konfigurasi aktif `config/config.yaml`.

## Berkas yang tersedia

- `config.yaml`
- `tau_u.yaml`

[Panduan utama](../README.md) · [Evaluasi dan reproduksibilitas](../EVALUATION.md)
