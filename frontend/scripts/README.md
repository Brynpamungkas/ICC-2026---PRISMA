# Launcher frontend

`run.mjs` membaca pengaturan API/frontend lalu menjalankan Next pada mode dev, build atau start. Ini launcher, bukan modul model.

## Penggunaan dan batas

Gunakan npm scripts dari `frontend/` atau launcher stack root. Environment PRISMA_CONFIG harus menunjuk profil yang benar; host/port tidak perlu di-hardcode ulang di komponen.

## Berkas yang tersedia

- `run.mjs`

[Panduan utama](../../README.md) · [Evaluasi dan reproduksibilitas](../../EVALUATION.md)
