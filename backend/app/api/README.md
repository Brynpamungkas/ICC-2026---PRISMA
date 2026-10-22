# API FastAPI

Router lima endpoint aplikasi: POST `/api/tanya`, POST `/api/klarifikasi`, GET `/api/katalog`, GET `/api/log/{id_log}`, GET `/api/kesehatan`.

## Penggunaan dan batas

Respons tanya/klarifikasi memakai envelope `{id_sesi, id_log, decision}`. Pembacaan log memerlukan `X-Session-ID`. Klarifikasi memeriksa sesi, log asal dan kandidat, lalu memakai bukti tersimpan; tidak membangkitkan jawaban baru. HTTP 200 tidak berarti keputusan selalu JAWAB. Pemeriksaan kesehatan membaca ketersediaan model/database.

## Berkas yang tersedia

- `routes.py`

[Panduan utama](../../../README.md) · [Evaluasi dan reproduksibilitas](../../../EVALUATION.md)
