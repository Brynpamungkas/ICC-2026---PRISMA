# Aplikasi backend

Komponen produksi: `main.py` memulai FastAPI, `orchestrator.py` merangkai K3, `conditions.py` menyediakan K1/K2, `catalog.py` membaca katalog, dan `eval_metrics.py` menghitung metrik.

## Penggunaan dan batas

Alur utama: pertanyaan → ekstraksi → kandidat → pemeriksaan → sampel SQL → eksekusi → voting → keputusan. Hanya S4 memakai model. Klarifikasi memakai bukti pilihan yang tersimpan.

## Subfolder

- [api](api/README.md)
- [llm](llm/README.md)
- [logging](logging/README.md)
- [schemas](schemas/README.md)
- [sqlguard](sqlguard/README.md)
- [steps](steps/README.md)

## Berkas yang tersedia

- `catalog.py`
- `conditions.py`
- `config.py`
- `eval_metrics.py`
- `main.py`
- `orchestrator.py`
- `suggest.py`
- `text.py`

[Panduan utama](../../README.md) · [Evaluasi dan reproduksibilitas](../../EVALUATION.md)
