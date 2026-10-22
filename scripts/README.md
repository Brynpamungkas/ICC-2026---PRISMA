# Utilitas data dan eksperimen

Skrip sumber untuk katalog/ETL, dataset, evaluator, pemeriksaan lingkungan dan smoke model sesuai yang benar-benar tersedia pada branch ini.

## Penggunaan dan batas

Entrypoint rilis adalah setup.sh/run.sh/check.sh pada root. Gunakan --help pada skrip Python untuk membaca opsi aktual. ETL, pembaruan label, kalibrasi dan inferensi menghasilkan/mengubah artefak; membaca README bukan izin mengeksekusinya. Skrip eval_lengkap.sh lama tidak diekspor karena jalur GPU mengandung operasi commit otomatis.

## Berkas yang tersedia

18 berkas sumber/artefak sebelum README tambahan: 13 .py, 5 .sh.

Contoh nama aktual: `build_catalog.py`, `catalog_lib.py`, `check_env.py`. Daftar lengkap tetap berada pada folder dan manifest sumber.

[Panduan utama](../README.md) · [Evaluasi dan reproduksibilitas](../EVALUATION.md)
