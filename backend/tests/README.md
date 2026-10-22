# Tes backend

Tes unit, integrasi, fixture dan golden dari versi sumber. Tes packaging tambahan berada di `release/tests/`.

## Penggunaan dan batas

Dari root: `PRISMA_CONFIG=config/config.yaml .venv/bin/python -B -m pytest backend/tests release/tests -q -p no:cacheprovider`. Tes fixture/mock tidak membuktikan model nyata bekerja. Tiga golden FROZEN pada snapshot rilis masih skipped; jangan menyatakan golden lulus seluruhnya.

## Subfolder

- [fixtures](fixtures/README.md)
- [golden](golden/README.md)
- [integration](integration/README.md)
- [unit](unit/README.md)

[Panduan utama](../../README.md) · [Evaluasi dan reproduksibilitas](../../EVALUATION.md)
