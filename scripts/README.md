# Utilitas data dan eksperimen

Skrip sumber untuk katalog/ETL, dataset, evaluator, pemeriksaan lingkungan dan smoke model sesuai yang benar-benar tersedia pada branch ini.

## Penggunaan dan batas

Entrypoint rilis adalah setup.sh/run.sh/check.sh pada root. Gunakan --help pada skrip Python untuk membaca opsi aktual. ETL, pembaruan label, kalibrasi dan inferensi menghasilkan/mengubah artefak; membaca README bukan izin mengeksekusinya. Skrip eval_lengkap.sh lama tidak diekspor karena jalur GPU mengandung operasi commit otomatis.

## Berkas yang tersedia

- `build_catalog.py`
- `catalog_lib.py`
- `check_env.py`
- `dataset_tools.py`
- `etl.py`
- `probe_m3.py`
- `run_eval.py`
- `serve_vllm.sh`
- `smoke_vllm.py`

[Panduan utama](../README.md) · [Evaluasi dan reproduksibilitas](../EVALUATION.md)
