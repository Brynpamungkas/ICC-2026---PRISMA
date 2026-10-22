# Templat dataset evaluasi (D10 C3–C4, D11 D3–D8)

**Status terbaru — 21 Oktober 2026:** pengguna memilih jalur M5 draf LLM ditinjau/disetujui manusia menurut pernyataannya. `../label_final.csv` berisi404 interpretasi VERIFIED atas180 soal, dengan SQL rujukan mekanis dan hasil read-only pada `../label_final.answers.jsonl`; rekam persetujuan dan hash `../review_final.json`. KerangkaA/B dan drafLLM asli tetap disimpan. Tidak ada label awal independen/kappa yang diklaim. Bagian dua penilai di bawah menjelaskan baseline paper dan pilihan sebelumnya, bukan bukti bahwa proses itu sudah dilakukan. VERIFIED lokal ini tidak otomatis berarti seluruh protokol paper terpenuhi.


Salin templat CSV ke berkas kerja penilai yang terpisah lalu isi. Templat JSON berisi nilai kosong dan bukan bukti. **Pertanyaan dan label ditulis manusia, bukan AI** (D11 D1: AI sebagai anotator = DI LUAR BASELINE). Berkas di folder ini adalah templat, bukan data atau bukti penelitian.

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
PRISMA_CONFIG=config/local.cpu.yaml bash scripts/eval_lengkap.sh dev <seed> # setelah label/protokol sah; hanya kandidat kalibrasi
PRISMA_CONFIG=config/local.cpu.yaml bash scripts/eval_lengkap.sh test <seed> # setelah pembekuan manusia dan hash sah
```

Label awal A dan B **tidak ditimpa** saat rekonsiliasi; buat `label_final.csv` baru.

## 4. Protokol dua penilai paper (pilihan sebelumnya; tetap tersedia)

Dua manusia mengerjakan label awal secara independen, tanpa melihat draf LLM, keluaran PRISMA, atau label rekannya. Kunci kedua berkas awal; hitung kappa keputusan sebelum rekonsiliasi. Draf LLM hanya boleh dibuka sesudah tahap itu untuk membantu diskusi. Keputusan akhir tetap berdasarkan manusia, definisi resmi, dan hasil kueri rujukan, bukan keluaran sistem.

Berkas `label_A.csv`, `label_B.csv`, `label_final.csv`, dan `label_draf_llm.csv` yang diimpor dari M5 belum membuktikan penilaian independen. Nama A/B pada berkas tidak membuktikan ada dua manusia. Pada saat impor semua label final masih DRAFT; status terkini mengikuti catatan jalur M5 di atas. Persetujuan dokumen tidak mengubah status itu menjadi VERIFIED.

Jika penilai sudah terpapar draf, catat paparan tersebut; jangan menyatakan independensi awal secara retrospektif. Tim perlu menyelesaikan dampaknya sebelum evaluasi final.

Salin `protocol.json` ke lokasi yang ditetapkan profil evaluasi hanya setelah bukti nyata tersedia. Isikan peninjau, urutan kerja yang benar, path dan SHA-256 dua label awal, laporan kappa awal, serta log rekonsiliasi. `scripts/eval_protocol.py` memeriksa hash dan menghitung ulang kesepakatan. Independensi manusia tetap memerlukan audit tim; pemeriksaan berkas tidak dapat membuktikannya sendiri.

Setiap perubahan label mencatat question_id, penilai/reviewer, nilai sebelum/sesudah, alasan, sumber, dan waktu. Simpan label awal terpisah. Jangan mengubah DRAFT secara massal untuk melewati pemeriksaan runner.

## 5. Pembekuan dan batas evaluasi

`freeze.json` adalah templat kosong. Setelah review dan commit yang diotorisasi terpisah, catat reviewer, commit bersih dan hash profil konfigurasi yang dipakai, tau, pertanyaan, split, label final, protokol anotasi dan prompt. Jalur test menolak prasyarat yang tidak lengkap. Skrip lokal tidak melakukan commit atau pembekuan otomatis.

180 pertanyaan impor saat ini bersumber `llm`, bukan 60 pertanyaan mahasiswa yang diminta paper. Komposisi 180 dan split 54/126 saja tidak membuktikan keabsahan sumber. Empat contoh dev tetap nonaktif karena reviewer sumber kosong; review contoh berbeda dari verifikasi label seluruh corpus.

Checker jawaban adaptasi mempertahankan kebijakan M5: teks diperiksa pada RANK, selain itu hanya angka. Kebijakan ini masih berisiko menerima pasangan wilayah/nilai yang tertukar pada hasil multiwilayah. Jangan memakai hasil checker sebagai label manusia atau mengklaim evaluasi final siap sebelum review batas tersebut.
