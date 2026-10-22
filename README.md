# PRISMA — vLLM NVIDIA

Aplikasi lokal tanya jawab data BPS berbahasa Indonesia. Keluaran JAWAB, TANYA dan TAHAN; Next.js + FastAPI + SQLite read-only.

Branch ini **release/vllm**, diekspor dari `c1e0900b26dfcd1f86c439cc96724d30ac0b45aa`. Versi lain tersedia pada branch `release/llama`. Dua versi dipisah karena prompt, SQL guard, T5, trace dan evaluator berbeda. Kode inti masing-masing dipertahankan; tidak ada penggabungan metode.

## Cepat di laptop Bryan yang sudah terpasang

```bash
cd /home/bryan/prisma-release-vllm
bash setup.sh --reuse /home/bryan/prisma-icc2026 --app-only
bash run.sh --external-model
```

Branch vLLM di laptop tanpa NVIDIA hanya dapat memeriksa API/UI/offline. --external-model tidak menyediakan model; model asli harus dilayani tersendiri pada alamat config. Health akan menyatakan tidak tersedia bila model belum hidup.

Buka **http://127.0.0.1:3000**. Tunggu model dan database tersedia lalu klik **Periksa lagi**. Ctrl+C menghentikan proses yang dimulai sesi launcher ini. Jangan menjalankan kedua versi sekaligus pada port yang sama.

## Mesin Linux atau WSL2 bersih

Prasyarat: Git, Python 3.11 beserta venv/pip, compiler C++ dan Make untuk build CPU, akses unduhan saat setup. Node 24.11.0 disediakan dan checksum diverifikasi. GPU membutuhkan driver NVIDIA yang sesuai; setup model memakai environment terpisah agar paket FastAPI model dan API tidak saling menimpa.

```bash
bash setup.sh --python /path/ke/python3.11
bash check.sh
bash run.sh
```

`/path/ke/python3.11` diganti path interpreter 3.11 yang benar. Setup tidak memakai sudo atau mengganti Python sistem. DB resmi yang cocok manifest sudah disertakan. Model dan environment tidak disertakan dalam Git; model diunduh/dibangun oleh setup saat diperlukan. Kegagalan hash menghentikan proses.

GPU: vLLM 0.32.0 dari snapshot lock model; AWQ revision 867d050da8a1af36b04fde627402656b3f918511, N64, empat contoh dev dan tau 0 sesuai run sumber. Setup lengkap/model hanya untuk mesin NVIDIA.

Pemisahan dependensi: `requirements-api.lock` adalah snapshot API/ETL/test Linux Python 3.11 yang diperiksa pada laptop ini; `requirements-model.lock` hanya ada pada branch GPU. Snapshot asal tim di `release/environment/` disimpan untuk penelusuran. `requirements-core.lock` historis Windows bukan lock lintas platform dan tidak dipakai entrypoint setup baru.

## Perintah penting

```bash
bash run.sh --check-only                 # preflight berkas; belum uji layanan hidup
bash check.sh                            # source parity, backend/tes rilis, lint, frontend/types/build
.venv/bin/python -B tools/release_cli.py replay  # hitung ulang hasil tersimpan tanpa model
```

Untuk runtime model yang sudah dinyalakan secara terpisah: `bash run.sh --external-model`. Pemeriksaan berkas tidak menggantikan demo nyata. Makna dan batas bukti: [EVALUATION.md](EVALUATION.md); hasil verifikasi penyiapan rilis ada pada laporan luar working tree yang diberikan bersama paket.

## Isi

- `backend/`, `frontend/`: implementasi dan tes dari versi sumber.
- `config/`: parameter asli; launcher memilih profil dari `release/profile.json`.
- `data/`: SQLite snapshot resmi, katalog, data mentah dan sumber BPS.
- `eval/annotations/`, `eval/testset/`: label, provenance, rujukan dan split yang diperlukan evaluator.
- `evidence/`: run dev/test/terputus serta bukti terkait yang dipertahankan; berkas bukan keluaran run baru.
- `paper/`: draf Bab IV–V untuk review, belum karya ilmiah final Bab I–V.
- `release/`: commit asal, checksum sumber, runtime dan snapshot dependensi.
- `tools/`: setup, launcher dan penghitungan ulang metrik. Tidak mengubah algoritma riset.

Dokumen D00–D18, riwayat prompt/chat, cache, entrypoint/bundle frontend statis lama dan folder environment tidak masuk ekspor ini. Repo pengembangan dan arsip lengkap tetap dipertahankan. Asal label LLM dan keterbatasan anotasi tetap dicatat; pembersihan tidak mengubah provenance penelitian atau kewajiban pernyataan penggunaan AI pada naskah.

Belum ada push/submit. Paket ini tidak otomatis meluluskan G7/G8 atau membuktikan semua laptop mampu menjalankan model.

CSS dan font pada frontend/src/style.css serta frontend/dist/ tetap disertakan karena diimpor Next.js; berkas tersebut bukan cache yang boleh dibuang.
