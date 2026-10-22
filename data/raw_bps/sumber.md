# Sumber data BPS

Kolom "Berkas" harus sama persis dengan nama berkas di folder ini (ETL mengeceknya).

| Berkas | Nama tabel | URL | Periode | Tanggal akses |
|---|---|---|---|---|
| Jumlah_dan_Persentase_Penduduk_Miskin_Menurut_Provinsi__2025.csv | Jumlah dan Persentase Penduduk Miskin Menurut Provinsi, 2025 (Susenas) | https://www.bps.go.id/id/statistics-table/3/UkVkWGJVZFNWakl6VWxKVFQwWjVWeTlSZDNabVFUMDkjMw==/jumlah-dan-persentase-penduduk-miskin-menurut-provinsi--2023.html?year=2025 | Maret & September 2025 | 17 Oktober 2026 |
| Persentase_Penduduk_Miskin__P0__Menurut_Provinsi_dan_Daerah__2026.csv | Persentase Penduduk Miskin (P0) Menurut Provinsi dan Daerah, 2026 (Susenas) | TODO: URL tabel P0 (yang lama sama dengan URL tabel 2025 di atas, kemungkinan salah tempel) | Maret 2026 (Semester 2 belum rilis) | 17 Oktober 2026 |
| Tingkat_Pengangguran_Terbuka__TPT__dan_Tingkat_Partisipasi_Angkatan_Kerja__TPAK__Menurut_Provinsi__2025.csv | TPT dan TPAK Menurut Provinsi, 2025 (Sakernas) | https://www.bps.go.id/id/statistics-table/3/V2pOVWJWcHJURGg0U2pONFJYaExhVXB0TUhacVFUMDkjMw==/tingkat-pengangguran-terbuka--tpt--dan-tingkat-partisipasi-angkatan-kerja--tpak--menurut-provinsi--2022.html?year=2025 | Februari & Agustus 2025 | 17 Oktober 2026 |
| Tingkat_Pengangguran_Terbuka_Menurut_Provinsi__2026.csv | Tingkat Pengangguran Terbuka Menurut Provinsi, 2026 (Sakernas) | https://www.bps.go.id/id/statistics-table/2/NTQzIzI=/tingkat-pengangguran-terbuka-menurut-provinsi.html | Februari 2026 (Agustus belum rilis) | 17 Oktober 2026 |
| Penduduk Berumur 15 Tahun ke Atas Menurut Provinsi dan Jenis Kegiatan Selama Seminggu Terakhir, 2025.csv | Penduduk Berumur 15 Tahun ke Atas Menurut Provinsi dan Jenis Kegiatan Selama Seminggu Terakhir, 2025 (Sakernas) | www.bps.go.id/id/statistics-table/3/VUVKUFpHeGpjVXh2V1dka1dtRkxSVXBaYW5KUVVUMDkjMyMwMDAw/penduduk-berumur-15-tahun-ke-atas-menurut-provinsi-dan-jenis-kegiatan-selama-seminggu-terakhir.html?year=2025 | Agustus 2025 | 17 Oktober 2026 |
| Angka Partisipasi Kasar (APK) Menurut Provinsi dan Jenjang Pendidikan, 2025.csv | Angka Partisipasi Kasar (APK) Menurut Provinsi dan Jenjang Pendidikan, 2025 (Susenas) | https://www.bps.go.id/id/statistics-table/2/MzAzIzI=/angka-partisipasi-kasar--apk--menurut-provinsi-dan-jenjang-pendidikan.html | 2025 (Susenas Maret; cek catatan tabel) | 17 Oktober 2026 |
| Angka Partisipasi Murni (APM) Menurut Provinsi dan Jenjang Pendidikan, 2025.csv | Angka Partisipasi Murni (APM) Menurut Provinsi dan Jenjang Pendidikan, 2025 (Susenas) | https://www.bps.go.id/id/statistics-table/2/MzA0IzI=/angka-partisipasi-murni--apm--menurut-provinsi-dan-jenjang-pendidikan.html | 2025 (Susenas Maret; cek catatan tabel) | 17 Oktober 2026 |
| Angka Partisipasi Sekolah (APS) Menurut Provinsi dan Kelompok Umur, 2025.csv | Angka Partisipasi Sekolah (APS) Menurut Provinsi dan Kelompok Umur, 2025 (Susenas) | https://www.bps.go.id/id/statistics-table/2/MjIxMSMy/angka-partisipasi-sekolah--aps--menurut-provinsi-dan-kelompok-umur.html | 2025 (Susenas Maret; cek catatan tabel) | 17 Oktober 2026 |

Tidak dipakai (angka nasional, bukan per provinsi): "Jumlah dan Persentase Penduduk Bekerja dan Pengangguran, 2026.csv" dan versi "(Triwulanan)".

## Asal kolom `definisi_resmi` di data/katalog/indikator.csv
Teks disalin dari Sirusa (sirusa.web.bps.go.id/metadata). Verifikasi ulang kata per kata dengan membuka halamannya sebelum snapshot final.

| Indikator | Entri Sirusa | Produsen data entri | Status |
|---|---|---|---|
| KMS_PERSEN | Persentase Penduduk Miskin, ID Indah 33401 | Direktorat Statistik Ketahanan Sosial (BPS) | Sumber BPS pusat |
| KMS_JUMLAH | Jumlah Penduduk Miskin, ID Indah 33400 | Direktorat Statistik Ketahanan Sosial (BPS) | Sumber BPS pusat |
| TPT_PERSEN | Tingkat Pengangguran Terbuka, ID Indah 22247 | Bappeda Provinsi Lampung | SEMENTARA, cari entri BPS pusat |
| PGR_JUMLAH | Jumlah Pengangguran, ID Indah 89579 | Dinas Tenaga Kerja dan Transmigrasi Kab. Barito Kuala | SEMENTARA, cari entri BPS pusat |
| APM_SD/SMP/SMA | Angka Partisipasi Murni (APM), ID Indah 132138 | Dinas Pendidikan dan Kebudayaan Kab. Sukamara | SEMENTARA, cari entri BPS pusat |
| APS_7_12/13_15/16_18 | Angka Partisipasi Sekolah (APS), indikator/2940 | Kegiatan: SUSENAS Kor (Tahunan) 2002 (produsen tidak tampil) | Sumber Susenas, teks dari ringkasan halaman |
| APK_SD/SMP/SMA | Angka Partisipasi Kasar (APK) pada kelompok umur, ID Indah 102617 | Pemerintah Kota Pariaman (level Kota Pariaman) | SEMENTARA, cari entri BPS pusat; teks asli menulis "dimasingmasing" |