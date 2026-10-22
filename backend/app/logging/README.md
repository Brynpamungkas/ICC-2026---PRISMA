# Log dan trace

Pencatatan LogRecord dalam JSONL. Isi yang tersedia mengikuti implementasi profil ini; log API dan arsip penelitian memiliki lingkup berbeda.

## Penggunaan dan batas

Log run baru mengikuti path pada konfigurasi dan ditulis di `eval/runs/`. Arsip historis berada di `evidence/`. ID log publik API dan run_id internal merupakan identitas berbeda. Jangan mengisi field jejak yang tidak pernah direkam.

Profil folder ini: **CPU llama.cpp/GGUF N8**, konfigurasi aktif `config/cpu.eval.yaml`.

Branch CPU menyediakan sidecar trace pipeline dan transport sesuai konfigurasi.

## Berkas yang tersedia

- `jsonl.py`
- `trace.py`

[Panduan utama](../../../README.md) · [Evaluasi dan reproduksibilitas](../../../EVALUATION.md)
