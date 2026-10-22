# PRISMA — llama.cpp CPU

Aplikasi lokal tanya jawab data BPS berbahasa Indonesia. Keluaran JAWAB, TANYA dan TAHAN; Next.js + FastAPI + SQLite read-only.

Branch ini **release/llama**, diekspor dari `4d8dfaa64cb2efff3e59239e6515365e4fd88f5c`. Versi lain tersedia pada branch `release/vllm`. Dua versi dipisah karena prompt, SQL guard, T5, trace dan evaluator berbeda. Kode inti masing-masing dipertahankan; tidak ada penggabungan metode.

## Susunan branch yang akan digunakan

Repositori final direncanakan memakai susunan berikut:

| Branch final | Runtime | Kedudukan |
|---|---|---|
| `main` | vLLM + Qwen2.5-Coder-1.5B-Instruct AWQ, N=64 | Versi utama; baseline runtime paper |
| `llama-version` | llama.cpp + Qwen2.5-Coder-1.5B-Instruct GGUF Q4_K_M, N=8 | Alternatif CPU untuk laptop tanpa NVIDIA; hasil dilaporkan terpisah |

Versi CPU memakai **llama.cpp**, bukan Ollama. Kedua versi mempertahankan kode, konfigurasi dan bukti sumber masing-masing; perbedaan prompt, validasi SQL, T5, trace dan evaluator tidak disatukan diam-diam. Angka hasil kedua profil bukan ablasi runtime/N terkontrol.

Paket persiapan lokal saat ini masih bernama `release/vllm` dan `release/llama`. Pemetaan menuju repositori final adalah `release/vllm` → `main`, serta `release/llama` → `llama-version`. Nama branch belum diubah oleh pembaruan README ini. Jangan memakai perintah checkout nama final sebelum branch tersebut benar-benar tersedia.

## Cepat di laptop Bryan yang sudah terpasang

```bash
cd /home/bryan/prisma-release
bash setup.sh --reuse /home/bryan/prisma-icc2026 --reuse-build
bash run.sh
```

Reuse memverifikasi GGUF dan commit llama.cpp, memakai environment/Node lokal melalui symlink yang diabaikan Git, menyalin dependensi frontend agar repo lama tidak disentuh, serta menyalin build lokal setelah hash source dan proxy dicocokkan. Ini bukan build baru.

Buka **http://127.0.0.1:3000**. Tunggu model dan database tersedia lalu klik **Periksa lagi**. Ctrl+C menghentikan proses yang dimulai sesi launcher ini. Jangan menjalankan kedua versi sekaligus pada port yang sama.

## Mesin Linux atau WSL2 bersih

Prasyarat: Git, Python 3.11 beserta venv/pip, compiler C++ dan Make untuk build CPU, akses unduhan saat setup. Node 24.11.0 disediakan dan checksum diverifikasi. GPU membutuhkan driver NVIDIA yang sesuai; setup model memakai environment terpisah agar paket FastAPI model dan API tidak saling menimpa.

```bash
bash setup.sh --python /path/ke/python3.11
bash check.sh
bash run.sh
```

`/path/ke/python3.11` diganti path interpreter 3.11 yang benar. Setup tidak memakai sudo atau mengganti Python sistem. DB resmi yang cocok manifest sudah disertakan. Model dan environment tidak disertakan dalam Git; model diunduh/dibangun oleh setup saat diperlukan. Kegagalan hash menghentikan proses.

CPU: llama.cpp dipatok commit 620d2225cc436ab0b001e3200e590e3b286ef9ab, GGUF Q4_K_M hash yang sama dengan run, N8 dan tau 0 dari dev. Hasilnya dilaporkan terpisah dari baseline vLLM.

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

`--reuse-build` menyalin build lokal yang telah ada setelah hash source UI, lock dan pengaturan proxy dicocokkan. Ini bukan klaim build baru. Tanpa flag tersebut setup melakukan build dari source.

Pemeriksaan rilis di shell AI: 44 tes frontend lulus per branch; build baru terhalang pembacaan stdout subproses TypeScript. Build lokal lama dipakai secara eksplisit hanya di laptop ini. Arsip Git tidak berisi build itu; mesin bersih tetap harus menjalankan setup/build.

## Panduan setiap folder

Tiap folder source dan arsip yang dilacak kini memiliki README. Folder dependensi, environment, cache/build dan output run baru yang diabaikan Git tidak diberi README manual. README tambahan di arsip menjelaskan bukti; tidak mengubah artefak aslinya.

| Folder | Panduan |
|---|---|
| `backend/` | [Backend PRISMA](backend/README.md) |
| `frontend/` | [Frontend Next.js](frontend/README.md) |
| `config/` | [Konfigurasi runtime dan evaluasi](config/README.md) |
| `data/` | [Snapshot data BPS](data/README.md) |
| `eval/` | [Evaluasi penelitian](eval/README.md) |
| `evidence/` | [Arsip bukti penelitian](evidence/README.md) |
| `paper/` | [Paper dan status naskah](paper/README.md) |
| `release/` | [Metadata rilis](release/README.md) |
| `scripts/` | [Utilitas data dan eksperimen](scripts/README.md) |
| `tools/` | [Alat penyiapan rilis](tools/README.md) |

Susunan final yang direncanakan: `main` = vLLM, `llama-version` = alternatif CPU. Paket persiapan masih memakai `release/vllm` dan `release/llama` sampai penamaan final diterapkan. Kesesuaian runtime tidak membuktikan seluruh evaluasi, anotasi, studi pengguna atau gerbang paper sudah lengkap.
