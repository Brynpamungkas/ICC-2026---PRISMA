# Templat dataset evaluasi (D10 C3–C4, D11 D3–D8)

Salin templat ke `eval/annotations/` lalu isi. **Pertanyaan dan label ditulis manusia, bukan AI** (D11 D1: AI sebagai anotator = DI LUAR BASELINE). Berkas di folder ini hanya header, bukan data.

## 1. `pertanyaan.csv` — satu baris per pertanyaan (180 baris)

| Kolom | Isi |
| --- | --- |
| question_id | ID unik stabil, mis. `KMS-001`, `KRJ-014`, `PDK-030` |
| domain | `kemiskinan` / `ketenagakerjaan` / `pendidikan` |
| target_group | kelompok yang dituju penulis: `TAK_AMBIGU` / `AMBIGU_TEKS` / `AMBIGU_ANGKA_SAMA` / `AMBIGU_ANGKA_BEDA`. Kelompok final ditentukan penilai dari hasil kueri rujukan |
| source_kind | `mahasiswa` (tepat 60 pertanyaan, dari mahasiswa ilmu sosial) / `tim` |
| source_record_id | ID pseudonim sumber (mis. `MHS-07`), tanpa nama asli |
| author | inisial penulis/pengumpul |
| question_text | teks asli, jangan diperbaiki diam-diam |

Target komposisi (paper Tabel VIII) — `cek-pertanyaan` menampilkan progres per sel:

| Kelompok | Kemiskinan | Ketenagakerjaan | Pendidikan |
| --- | --- | --- | --- |
| TAK_AMBIGU | 20 | 20 | 15 |
| AMBIGU_TEKS | 20 | 20 | 15 |
| AMBIGU_ANGKA_SAMA | 0 | 0 | 30 |
| AMBIGU_ANGKA_BEDA | 20 | 20 | 0 |

Makna kelompok (struktur hasil kueri rujukan):
- **TAK_AMBIGU**: satu interpretasi sah.
- **AMBIGU_TEKS**: beberapa interpretasi sah yang hasilnya memuat kolom teks (mis. nama provinsi) — contoh pola: "provinsi paling miskin" (persentase vs jumlah).
- **AMBIGU_ANGKA_SAMA**: beberapa interpretasi, hasil angka dengan satuan sama (mis. APK/APM/APS, semuanya %).
- **AMBIGU_ANGKA_BEDA**: beberapa interpretasi, hasil angka dengan satuan berbeda (mis. % vs ribu jiwa).

Dilarang memakai 6 pertanyaan probe M3 (`scripts/probe_m3.py`); pemeriksa menolaknya.

## 2. `label_<PENILAI>.csv` — satu berkas per penilai, satu baris per interpretasi sah

Dua penilai mengisi **terpisah**, tanpa melihat label penilai lain atau keluaran PRISMA (D11 D3/D6).

| Kolom | Isi |
| --- | --- |
| question_id | dari `pertanyaan.csv` |
| annotator_id | pseudonim penilai (`A` / `B`), sama di seluruh berkas |
| question_group | kelompok final menurut penilai (sama di semua baris satu pertanyaan) |
| decision_reference | `JAWAB` atau `TANYA` (sama di semua baris satu pertanyaan). TAHAN bukan label utama |
| interpretation_id | `I1`, `I2`, … unik per pertanyaan |
| meaning | parafrasa makna interpretasi |
| indicator_code | kode dari `data/katalog/indikator.csv` |
| region_codes | kode provinsi dipisah `;` (kosong = semua provinsi) |
| period | `YYYY-MM`; boleh dikosongkan → `buat-sql` mengisi periode terbaru yang tersedia bagi semua interpretasi pertanyaan itu (paper III-C) dan menandainya untuk diverifikasi |
| operation | `NONE` / `SUM` / `AVG` / `RANK_DESC_k` (k tertinggi) / `RANK_ASC_k` (k terendah), mis. `RANK_DESC_1` |
| reference_sql | SELECT yang ditulis/diverifikasi manusia; boleh memakai literal, mis. `kode_indikator='KMS_PERSEN'`. Keluarkan **hanya** `provinsi.nama` (bila jawabannya menyebut provinsi) dan `nilai`, urutkan bila operasinya peringkat; jangan menambah kolom kode/satuan. Pemeriksa jawaban membandingkan isi baris, bukan nama kolom; nama provinsi hanya dinilai untuk operasi `RANK` |
| rationale | alasan (RUB-01–RUB-06) |
| uncertainty_notes | ketidakpastian; tulis `tidak ada` bila memang tidak ada |
| source_refs | berkas/URL/tabel BPS yang dirujuk |
| verification_status | `DRAFT` / `NEEDS_REVIEW` / `VERIFIED` |

TANYA wajib punya ≥2 interpretasi. JAWAB dengan >1 interpretasi: jelaskan di rationale mengapa jawabannya tetap dapat dipakai.

## 3. Alur kerja

**Cara cepat bagi penilai:** isi kolom terstruktur (indicator_code, region_codes, period, operation) dan biarkan `reference_sql` kosong; `buat-sql` menyusun SQL rujukan secara deterministik. Penilai tetap memeriksa SQL dan hasilnya (`cek-label`). Lembar bantu (indikator, satuan, periode, istilah ambigu, kode provinsi): `python scripts/dataset_tools.py katalog`.

```bash
python scripts/dataset_tools.py katalog > eval/annotations/lembar_katalog.txt
python scripts/dataset_tools.py buat-sql eval/annotations/label_A.csv
# progres komposisi (boleh dijalankan berkali-kali selama menulis)
python scripts/dataset_tools.py cek-pertanyaan eval/annotations/pertanyaan.csv
# tiap penilai: periksa label + eksekusi kueri rujukan ke data/prisma.sqlite -> label_A.answers.jsonl
python scripts/dataset_tools.py cek-label eval/annotations/label_A.csv --pertanyaan eval/annotations/pertanyaan.csv
# kappa keputusan JAWAB/TANYA pada label AWAL, sebelum rekonsiliasi (D11 ANN-10)
python scripts/dataset_tools.py kappa eval/annotations/label_A.csv eval/annotations/label_B.csv > eval/annotations/kappa_awal.json
# setelah rekonsiliasi -> label_final.csv; seed disepakati tim dulu dan dicatat di D13
python scripts/dataset_tools.py split eval/annotations/pertanyaan.csv eval/annotations/label_final.csv --seed <seed>
# atau langkah 4-7 sekaligus (vLLM menyala):
bash scripts/eval_lengkap.sh dev <seed>     # split, run dev K3, kalibrasi tau, commit beku
bash scripts/eval_lengkap.sh test <seed>    # run test K1 K2 K3 + metrik
```

Label awal A dan B **tidak ditimpa** saat rekonsiliasi; buat `label_final.csv` baru.

## 4. Verifikasi draf LLM (keputusan tim 21 Okt)

`label_final.csv` berisi draf LLM (180 soal). Kolom `hasil_draf` menampilkan hasil kueri tiap tafsir. Untuk setiap soal:

1. Baca `question_text`. Apakah tafsir (baris I1, I2, ...) lengkap dan masuk akal? Tambah/hapus baris bila perlu.
2. Periksa `indicator_code`, `region_codes`, `period`, `operation` tiap baris. Bila mengubah salah satunya, **kosongkan `reference_sql`** (biasanya sudah kosong).
3. Periksa `decision_reference` (JAWAB/TANYA) dan `question_group`, sama di semua baris soal itu.
4. Bila sudah benar, ubah `verification_status` semua baris soal itu menjadi `VERIFIED`.

Jangan mengubah `label_draf_llm.csv` (dipakai untuk laporan koreksi). Setelah verifikasi:

```bash
python scripts/dataset_tools.py buat-sql eval/annotations/label_final.csv
python scripts/dataset_tools.py cek-label eval/annotations/label_final.csv --pertanyaan eval/annotations/pertanyaan.csv
python scripts/dataset_tools.py laporan-koreksi eval/annotations/label_draf_llm.csv eval/annotations/label_final.csv > eval/annotations/laporan_koreksi.json
```

