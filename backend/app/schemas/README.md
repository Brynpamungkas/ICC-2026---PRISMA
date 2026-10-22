# Kontrak data backend

Model Pydantic internal dan envelope API terdapat pada `models.py` dan `api.py`. Kontrak menyatukan ekstraksi, kandidat, kerangka SQL, hasil, voting, bukti, keputusan dan log.

## Penggunaan dan batas

Jaga tipe asli: angka tetap numerik dan NULL tetap null. Perubahan nama, tipe atau invariant perlu analisis dampak API/UI/tes dan persetujuan kontrak tersendiri. README ini tidak mengubah kontrak.

## Berkas yang tersedia

- `api.py`
- `models.py`

[Panduan utama](../../../README.md) · [Evaluasi dan reproduksibilitas](../../../EVALUATION.md)
