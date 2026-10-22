# Data BPS yang dipakai

Berkas asli ada di folder ini. Asal tiap berkas (URL, periode, tanggal akses) dicatat di `sumber.md`; hash tiap berkas dicatat otomatis di `data/etl_report.json`.

| Berkas | Indikator katalog | Periode |
|---|---|---|
| Jumlah_dan_Persentase_Penduduk_Miskin_Menurut_Provinsi__2025.csv | KMS_JUMLAH, KMS_PERSEN | 2025-03, 2025-09 |
| Persentase_Penduduk_Miskin__P0__Menurut_Provinsi_dan_Daerah__2026.csv | KMS_PERSEN | 2026-03 |
| Tingkat_Pengangguran_Terbuka__TPT__dan_Tingkat_Partisipasi_Angkatan_Kerja__TPAK__Menurut_Provinsi__2025.csv | TPT_PERSEN | 2025-02, 2025-08 |
| Tingkat_Pengangguran_Terbuka_Menurut_Provinsi__2026.csv | TPT_PERSEN | 2026-02 |
| Penduduk Berumur 15 Tahun ke Atas Menurut Provinsi dan Jenis Kegiatan Selama Seminggu Terakhir, 2025.csv | PGR_JUMLAH | 2025-08 |
| Angka Partisipasi Kasar (APK) Menurut Provinsi dan Jenjang Pendidikan, 2025.csv | APK_SD, APK_SMP, APK_SMA | 2025-03 |
| Angka Partisipasi Murni (APM) Menurut Provinsi dan Jenjang Pendidikan, 2025.csv | APM_SD, APM_SMP, APM_SMA | 2025-03 |
| Angka Partisipasi Sekolah (APS) Menurut Provinsi dan Kelompok Umur, 2025.csv | APS_7_12, APS_13_15, APS_16_18 | 2025-03 |

Kolom yang belum dirilis ("-" pada berkas 2026) tidak dimasukkan. Kolom di luar katalog (TPAK, APS 19-23) tidak dibaca.

## Memperbarui data
1. Taruh berkas baru di folder ini, tambahkan ke `manifest.yaml` (format di `manifest.example.yaml`; `python scripts/etl.py --inspect <berkas>` menampilkan indeks baris dan kolom) dan ke `sumber.md`.
2. `python scripts/etl.py --draft`, lalu `python scripts/build_catalog.py --suggest-coverage --db data/prisma.draft.sqlite` untuk memperbarui `cakupan_wilayah` dan `periode_tersedia` di `indikator.csv`.
3. `python scripts/build_catalog.py --validate`, `python scripts/etl.py`, `python scripts/build_catalog.py --version`.

## Masih terbuka
- Periode pendidikan (`2025-03`) adalah asumsi Susenas Maret; cocokkan dengan catatan tabel BPS (K-18).
- Kode provinsi Papua (91-96) mengikuti skema Kepmendagri; cocokkan dengan kode wilayah BPS.
- Definisi TPT, pengangguran, APM, dan APK di `indikator.csv` bersumber dari entri Sirusa milik daerah (lihat `sumber.md`); ganti dengan entri BPS pusat bila ada.
- Ketentuan penggunaan data BPS untuk repositori yang dikumpulkan.