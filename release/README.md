# Metadata rilis

`profile.json` memilih runtime/profil; `source_manifest.json` mencatat commit, path dan SHA-256 source serta artefak historis. Folder environment mempertahankan snapshot dependensi sumber.

## Penggunaan dan batas

README tambahan tidak mengubah daftar hash artefak asli. Verifikasi: `.venv/bin/python -B tools/release_cli.py verify` dari root. Identitas commit sumber berbeda dari commit repository rilis.

## Subfolder

- [environment](environment/README.md)
- [tests](tests/README.md)

## Berkas yang tersedia

- `profile.json`
- `source_manifest.json`

[Panduan utama](../README.md) · [Evaluasi dan reproduksibilitas](../EVALUATION.md)

## Susunan branch repository

- `main`: versi utama vLLM/AWQ/N64.
- `llama-version`: alternatif CPU llama.cpp/GGUF/N8.

Nama branch lokal sudah diterapkan untuk repository tujuan Brynpamungkas/ICC-2026---PRISMA. Penggantian nama tidak mengubah commit sumber, SHA-256 model atau parameter profil. Status unggahan diperiksa terpisah; remote yang dikonfigurasi belum berarti push berhasil.
