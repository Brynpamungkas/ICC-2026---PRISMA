# PRISMA

**PRISMA** adalah aplikasi tanya jawab data BPS berbahasa Indonesia yang berjalan sepenuhnya di komputer sendiri. Pengguna mengetik pertanyaan biasa, misalnya *"Berapa persentase penduduk miskin di Papua?"*, dan PRISMA menjawab dari basis data resmi BPS. Tidak ada layanan awan dan tidak ada data yang keluar dari mesin.

Keistimewaannya ada pada pertanyaan yang **ambigu**. Kalau sebuah pertanyaan punya beberapa tafsir yang sah *dan* tafsir-tafsir itu menghasilkan jawaban yang berbeda, PRISMA bertanya balik. Kalau semua tafsir menghasilkan jawaban yang sama, PRISMA langsung menjawab tanpa menanyai pengguna.

## 3 Outputs

| Keluaran | Arti |
|---|---|
| **JAWAB** | Pertanyaan jelas, atau semua tafsirnya menghasilkan angka yang sama. Jawaban ditampilkan beserta sumbernya. |
| **TANYA** | Ada tafsir yang jawabannya berbeda. PRISMA meminta pengguna memilih tafsir mana yang dimaksud. |
| **TAHAN** | PRISMA tidak cukup yakin atau kuerinya tidak lolos pemeriksaan keamanan, sehingga tidak memberi jawaban. Diberi kode alasan (T0–T5). |

Basis data hanya dibaca (read-only). Model bahasa tidak mengarang angka. Ia hanya menyusun kueri SQL, yang diperiksa dulu oleh validator sebelum dijalankan.

## Cakupan data

Data bersumber dari tabel BPS (disertakan di `data/raw_bps/`) untuk 38 provinsi, dalam tiga domain:

- **Kemiskinan**: persentase dan jumlah penduduk miskin.
- **Ketenagakerjaan**: tingkat pengangguran terbuka (TPT) dan jumlah pengangguran.
- **Pendidikan**: APK dan APM (SD, SMP, SMA) serta APS (7–12, 13–15, 16–18 tahun).

Contoh pertanyaan yang bisa dicoba:

- "Jumlah penduduk miskin di Papua pada September 2025?"
- "Lima provinsi dengan jumlah pengangguran terbanyak?"
- "Provinsi mana yang paling miskin?"
- "Bandingkan APK SMA di Jawa Barat dan Jawa Timur."

## Kebutuhan sistem

| Komponen | Keterangan |
|---|---|
| OS | Linux atau WSL2 (Windows). Setup tidak memakai `sudo`. |
| Python | 3.11 beserta `venv` dan `pip` |
| GPU | NVIDIA dengan VRAM sekitar 8 GB (model dilayani vLLM) |
| Lainnya | Git, koneksi internet saat setup (mengunduh model dan dependensi) |
| Node.js | 24.11.0, diunduh dan diverifikasi checksum-nya oleh setup |

Branch `main` memerlukan GPU NVIDIA. Untuk laptop tanpa GPU, tersedia alternatif CPU berbasis llama.cpp pada branch `llama-version`. Keduanya memakai port yang sama, jadi jangan dijalankan bersamaan.

## Memulai

```bash
git clone --branch main https://github.com/Brynpamungkas/ICC-2026---PRISMA.git
cd ICC-2026---PRISMA

bash setup.sh --python /path/ke/python3.11   # membuat .venv, memasang dependensi, mengunduh model
bash check.sh                                # tes backend, lint, tes dan build frontend
bash run.sh                                  # menjalankan model, backend, dan frontend
```

Ganti `/path/ke/python3.11` dengan lokasi Python 3.11 di mesin kamu (cek dengan `which python3.11`). Model dan lingkungan tidak ada di Git, tapi diunduh oleh setup, dan kegagalan pencocokan hash menghentikan proses.

Setelah `run.sh` berjalan, buka **http://127.0.0.1:3000**. Kalau halaman menyatakan model belum tersedia, tunggu model selesai dimuat lalu klik **Periksa lagi**. Tekan `Ctrl+C` untuk menghentikan semua proses yang dimulai oleh `run.sh`.

| Layanan | Alamat |
|---|---|
| Antarmuka (frontend) | http://127.0.0.1:3000 |
| API (backend) | http://127.0.0.1:8001 |
| Model (vLLM) | http://localhost:8000 |

Kalau model sudah dilayani secara terpisah, pakai `bash run.sh --external-model`. Untuk memeriksa berkas tanpa menyalakan layanan: `bash run.sh --check-only`.

## Cara memakai

1. Ketik pertanyaan pada kolom input.
2. Kalau hasilnya **JAWAB**, angka tampil beserta indikator, wilayah, dan periodenya.
3. Kalau hasilnya **TANYA**, pilih tafsir yang kamu maksud, lalu jawaban ditampilkan.
4. Kalau hasilnya **TAHAN**, baca kode alasannya, lalu ubah pertanyaan agar lebih spesifik (sebut indikator, provinsi, dan periode).

## Hasil evaluasi

Evaluasi memakai 180 pertanyaan (54 dev dan 126 test) dengan 404 interpretasi berlabel. Angka berikut dari split **test** (126 pertanyaan), konfigurasi dibekukan sebelum test dibuka.

| Kondisi | Perilaku | TKS ↓ | PBT ↓ | F1 TANYA ↑ | EX ↑ | TAHAN |
|---|---|---|---|---|---|---|
| K1 | selalu menjawab, tanpa klarifikasi | 14,3% | 0% | 0,00 | 2,6% | 84,9% |
| K2 | selalu bertanya saat ada tafsir ganda | 0,8% | 18,2% | 0,95 | 71,1% | 6,3% |
| **K3 (PRISMA)** | bertanya hanya jika jawaban berbeda | **1,6%** | **0%** | **0,94** | **76,3%** | 14,3% |

- **TKS**: proporsi pertanyaan yang dijawab sistem padahal seharusnya ditanya, atau jawabannya salah.
- **PBT**: proporsi pertanyaan yang sebenarnya cukup dijawab tapi malah ditanya balik.
- **F1 TANYA**: ketepatan memutuskan kapan harus bertanya.
- **EX**: ketepatan jawaban pada pertanyaan yang tidak ambigu.
- Latensi K3: median sekitar 2,8 detik, persentil ke-95 sekitar 5,6 detik per pertanyaan.

K3 mempertahankan PBT 0% (tidak menanyai pengguna tanpa perlu) dengan TKS yang hampir setara K2. Harga yang dibayar adalah 14,3% keputusan TAHAN, yang sebagian besar (12,7% dari seluruh pertanyaan) disebabkan validator SQL menolak kerangka kueri yang tidak sesuai bentuk yang diizinkan. Untuk membaca batas klaim, lihat bagian berikut.

Hasil ini bisa dihitung ulang dari berkas tersimpan tanpa model:

```bash
.venv/bin/python -B tools/release_cli.py replay
```

## Struktur repositori

| Folder | Isi |
|---|---|
| `backend/` | API FastAPI, pipeline tujuh langkah (S1–S7), validator SQL, dan tes |
| `frontend/` | Antarmuka Next.js |
| `config/` | `config.yaml` (parameter) dan `tau_u.yaml` (ambang kedekatan angka per satuan) |
| `data/` | Basis data SQLite, katalog indikator dan kamus istilah, data mentah BPS |
| `eval/` | Pertanyaan, label, dan pembagian dev/test |
| `evidence/` | Run evaluasi yang sudah selesai beserta metriknya |
| `paper/` | Draf Bab IV–V |
| `scripts/` | ETL, pembuatan katalog, dan alat evaluasi |
| `tools/`, `release/` | Setup, launcher, dan metadata rilis |

Tiap folder punya `README.md` sendiri.

## Perintah berguna

```bash
make test      # jalankan tes backend dan rilis
make lint      # ruff
make check     # tes + lint + tes dan build frontend
make replay    # hitung ulang metrik dari bukti tersimpan
```

## Sumber data dan lisensi komponen

Angka berasal dari tabel resmi BPS dan tidak diubah. Ketentuan pemakaian data mengikuti sumber BPS (lihat `data/raw_bps/sumber.md`). Model Qwen2.5-Coder-1.5B-Instruct-AWQ, vLLM, llama.cpp, Next.js, dan dependensi lain mengikuti lisensi masing-masing. Rincian ada di [THIRD_PARTY.md](THIRD_PARTY.md).
