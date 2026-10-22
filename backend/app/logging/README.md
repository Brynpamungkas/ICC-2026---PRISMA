# Log dan trace

Pencatatan LogRecord dalam JSONL. Isi yang tersedia mengikuti implementasi profil ini; log API dan arsip penelitian memiliki lingkup berbeda.

## Penggunaan dan batas

Log run baru mengikuti path pada konfigurasi dan ditulis di `eval/runs/`. Arsip historis berada di `evidence/`. ID log publik API dan run_id internal merupakan identitas berbeda. Jangan mengisi field jejak yang tidak pernah direkam.

Profil folder ini: **NVIDIA vLLM/AWQ N64**, konfigurasi aktif `config/config.yaml`.

Branch GPU sumber belum menyertakan modul trace CPU atau arsip seluruh respons mentah/vektor; README tidak menambahkan bukti tersebut.

## Berkas yang tersedia

- `jsonl.py`

[Panduan utama](../../../README.md) · [Evaluasi dan reproduksibilitas](../../../EVALUATION.md)
