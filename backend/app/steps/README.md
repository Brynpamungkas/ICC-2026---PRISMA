# Tujuh langkah PRISMA

S1 ekstraksi, S2 resolusi kandidat, S3 pemeriksaan kandidat, S4 sampling kerangka SQL, S5 eksekusi, S6 voting vektor, S7 keputusan. Masing-masing diimplementasikan pada berkas `s1_...` hingga `s7_...`.

## Penggunaan dan batas

S1–S3 dan S5–S7 tidak memanggil model. Voting memilih vektor seluruh kandidat, bukan pemenang berbeda per kandidat. JAWAB/TANYA/TAHAN mengikuti hasil pemeriksaan dan perbandingan; jumlah kandidat klarifikasi tidak dibatasi dua.

## Berkas yang tersedia

- `s1_extract.py`
- `s2_resolve.py`
- `s3_checks.py`
- `s4_sample.py`
- `s5_execute.py`
- `s6_vote.py`
- `s7_decide.py`

[Panduan utama](../../../README.md) · [Evaluasi dan reproduksibilitas](../../../EVALUATION.md)
