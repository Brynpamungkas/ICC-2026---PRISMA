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

## Pemetaan branch persiapan ke repositori final

- `release/vllm` → `main`: versi utama vLLM/AWQ/N64.
- `release/llama` → `llama-version`: alternatif CPU llama.cpp/GGUF/N8.

Ini rencana penamaan yang dipilih pemilik proyek. README tidak mengganti branch atau field commit pada metadata. SHA-256 model dan parameter masing-masing profil tetap mengikuti sumbernya.
