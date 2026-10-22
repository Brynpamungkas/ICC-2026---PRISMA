# Klien dan prompt model

Transport ke penyaji model, penyusunan prompt, pemuatan contoh dev, serta klien mock untuk tes. `mock.py` dipakai untuk pengujian, bukan pengganti model pada demo nyata.

## Penggunaan dan batas

Model menghasilkan kerangka SQL; hasilnya tetap diperiksa SQL guard dan dieksekusi pada data aktual. Parameter sampling dibaca dari profil konfigurasi. Duplikat sampel tetap merupakan suara; jangan melakukan deduplikasi sebelum voting.

Profil folder ini: **CPU llama.cpp/GGUF N8**, konfigurasi aktif `config/cpu.eval.yaml`.

## Berkas yang tersedia

- `client.py`
- `examples.py`
- `mock.py`
- `prompt.py`

[Panduan utama](../../../README.md) · [Evaluasi dan reproduksibilitas](../../../EVALUATION.md)
