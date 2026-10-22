# API client frontend

Adapter request/response dan tesnya: envelope keputusan, korelasi sesi/log, katalog, kesehatan dan klarifikasi.

## Penggunaan dan batas

Sesi acak berada di memori halaman; profil tamu tidak menjadi identitas login. Pembacaan log mengirim X-Session-ID. Jangan menampilkan respons usang untuk pertanyaan aktif atau mengisi metadata yang hilang dengan jawaban mock.

## Berkas yang tersedia

- `api.test.ts`
- `api.ts`

[Panduan utama](../../README.md) · [Evaluasi dan reproduksibilitas](../../EVALUATION.md)
