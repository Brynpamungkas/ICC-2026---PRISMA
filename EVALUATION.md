# Hasil dan reproduksibilitas

Commit sumber dan SHA-256 setiap file tercatat pada `release/source_manifest.json`. `evidence/` memuat hasil yang telah ada, termasuk run terputus. Manifest asli tetap menunjuk commit dan path pada repo pengembangan; tidak diganti menjadi commit rilis.

## Penghitungan ulang hasil tersimpan

```bash
.venv/bin/python -B tools/release_cli.py replay
```

Perintah memverifikasi sumber/bukti, memuat label dan jawaban SQL rujukan, menghitung ulang metrik dari semua 126 record K1/K2/K3, dan mencocokkan seluruh rincian dengan metrik tersimpan. Laporan baru ditulis ke `eval/runs/release-replay-*`, tidak menimpa bukti. Ini bukan inferensi ulang atau replay semua sampel GPU.

CPU memakai llama.cpp/GGUF/N8/prompt0.3.0-cpu.1 tanpa contoh; GPU memakai vLLM/AWQ/N64/prompt0.3.0 dengan empat contoh dev. Ada perbedaan SQL guard, T5, trace dan checker. Jangan menyebut perbandingan dua profil ini sebagai ablasi runtime/N terkontrol.

Corpus 180 pertanyaan, dev 54/test 126, label 404 interpretasi; pertanyaan bersumber LLM dan label final draf LLM ditinjau manusia. Tidak ada kappa/dua label awal independen yang diklaim hanya karena CSV berstatus VERIFIED. Studi pengguna dan ablasi lengkap belum dibuktikan oleh bukti ini.

## Inferensi baru dan pembekuan

Kode evaluator asli pada `scripts/run_eval.py` dipertahankan. Contoh perintah/metode dapat dibaca melalui `--help`. Pada CPU, guard test mengharuskan freeze, commit bersih dan checksum yang sesuai. Rilis memiliki commit baru; manifest freeze penelitian lama tidak boleh dipalsukan atau dipromosikan menjadi freeze rilis. Guard tersebut tidak dilemahkan. Inferensi test baru memerlukan pembekuan rilis yang sah melalui tugas tersendiri. Penghitungan metrik tersimpan dan aplikasi tidak memerlukan pembekuan baru itu.

Skrip `eval_lengkap.sh` lama tidak menjadi entrypoint rilis. Versi GPU mengandung operasi commit otomatis; rilis tidak mengaktifkannya. Jangan mengubah tau, contoh atau label memakai test yang telah dibuka untuk memperbaiki hasil penelitian lama.

## Lingkup verifikasi

Tes fixture/mock, pemeriksaan byte sumber, build frontend, hitung ulang metrik, dan demo model nyata memiliki bukti berbeda. Paket tidak menganggap tes offline sebagai bukti model NVIDIA bekerja pada laptop CPU. Hasil tes rilis dicatat terpisah dari hasil historis; kegagalan tidak dihapus.
