# Frontend Next.js

Next.js App Router + TypeScript. Tampilan tim dipertahankan, dengan kartu JAWAB/TANYA/TAHAN, pemilihan indikator, katalog, health dan pembacaan log melalui API.

## Penggunaan dan batas

Cara termudah adalah `bash run.sh` dari root setelah setup. Browser mengakses `/api`, lalu Next meneruskan ke API FastAPI. Tombol kirim memerlukan status model/database siap. Status siap bukan jaminan semua SQL/jawaban benar.

Profil folder ini: **CPU llama.cpp/GGUF N8**, konfigurasi aktif `config/cpu.eval.yaml`.

Untuk tes frontend saja, jalankan dari root setelah setup:

```bash
export PRISMA_CONFIG="$PWD/config/cpu.eval.yaml"
export PATH="$PWD/.local/node-v24.11.0-linux-x64/bin:$PATH"
cd frontend
npm test
npm run typecheck
npm run build
```

Perintah di atas mengasumsikan Linux x64/WSL2 dan Node lokal hasil setup. Build menghasilkan `.next/` dan bukan bukti model nyata.

## Subfolder

- [app](app/README.md)
- [components](components/README.md)
- [dist](dist/README.md)
- [lib](lib/README.md)
- [scripts](scripts/README.md)
- [src](src/README.md)

## Berkas yang tersedia

- `next-env.d.ts`
- `next.config.ts`
- `package-lock.json`
- `package.json`
- `tsconfig.json`
- `vitest.config.ts`

[Panduan utama](../README.md) · [Evaluasi dan reproduksibilitas](../EVALUATION.md)
