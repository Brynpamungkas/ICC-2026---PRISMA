# Corpus, label dan rujukan

Corpus aktual berisi 180 pertanyaan bersumber LLM dan 404 interpretasi final berstatus VERIFIED berdasarkan review manusia yang tercatat. SQL dan hasil rujukan tersimpan pada berkas final terkait.

## Penggunaan dan batas

Nama label_A/label_B serta status VERIFIED tidak membuktikan dua penilaian awal independen atau kappa. Jangan memakai keluaran PRISMA sebagai ground truth. README pada templates dipertahankan dari sumber dan dapat memuat petunjuk historis; entrypoint rilis adalah panduan root, bukan skrip lama yang tidak diekspor.

## Subfolder

- [templates](templates/README.md)

## Berkas yang tersedia

- `contoh_dev.json`
- `label_A.csv`
- `label_B.csv`
- `label_draf_llm.csv`
- `label_final.answers.jsonl`
- `label_final.csv`
- `laporan_koreksi.json`
- `lembar_katalog.txt`
- `pertanyaan.csv`

[Panduan utama](../../README.md) · [Evaluasi dan reproduksibilitas](../../EVALUATION.md)
