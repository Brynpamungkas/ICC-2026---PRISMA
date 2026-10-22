"""Langkah 7: kesetaraan (Tabel VII, persamaan 4) dan keputusan (persamaan 5).
- hasil memuat kolom teks : setara bila urutan nilai kolom teks identik (E(r)); angka tidak jadi syarat tambahan
- angka, satuan sama      : setara bila selisih absolut tiap nilai <= tau_u (dibandingkan semua pasangan)
- angka, satuan berbeda   : tidak pernah setara
PROPOSED (K-16/K-17, belum dibekukan): bentuk berbeda (teks vs angka, jumlah nilai berbeda) -> tidak setara (TANYA);
hasil berstatus galat/timeout/terpotong -> TAHAN T0 (bukan dianggap kosong atau setara). tau yang null -> ConfigError."""
from __future__ import annotations

from itertools import combinations

from backend.app.config import ConfigError
from backend.app.schemas import Candidate, Decision, Evidence, ExecResult, VoteResult


def no_value(r: ExecResult) -> bool:
    """K-16 (keputusan tim 20 Okt 2026): hasil tanpa baris, atau semua sel bukan-teks bernilai NULL (mis. AVG atas nol
    baris), tidak memuat nilai. Status galat tetap terpisah dan tidak dianggap kosong."""
    if not r.rows:
        return True
    num = [i for i, c in enumerate(r.columns) if c not in {"wilayah", "periode"}]
    return bool(num) and all(row[i] is None for row in r.rows for i in num)

def tahan(reason: str, suggestion: str, period_used: str | None = None) -> Decision:
    return Decision(decision="TAHAN", reason_code=reason, suggestion=suggestion, period_used=period_used)


def _text_values(r: ExecResult) -> list:
    idx = [i for i, c in enumerate(r.columns) if c in {"wilayah", "periode"}]
    return [row[i] for row in r.rows for i in idx]


def _numeric_values(r: ExecResult) -> list:
    idx = [i for i, c in enumerate(r.columns) if c not in {"wilayah", "periode"}]
    return [row[i] for row in r.rows for i in idx]


def setara(a: ExecResult, b: ExecResult, tau: dict[str, float | None]) -> bool:
    if a.structure != b.structure:
        return False
    if a.structure == "TEXT":
        return _text_values(a) == _text_values(b)
    if a.unit != b.unit:
        return False
    t = tau.get(a.unit)
    if t is None:
        raise ConfigError(f"tau_u untuk satuan {a.unit!r} belum dikalibrasi (jangan memakai nilai bawaan atau data uji)")
    if _text_values(a) != _text_values(b):
        return False
    xa, xb = _numeric_values(a), _numeric_values(b)
    if len(xa) != len(xb) or any(v is None for v in xa + xb):
        return False
    return all(abs(p - q) <= t for p, q in zip(xa, xb))


def decide(votes: list[VoteResult], tau: dict[str, float | None], *, candidates: dict[str, Candidate] | None = None,
           period_used: str | None = None) -> Decision:
    if not votes:
        return tahan("T4", "Coba rumuskan pertanyaan dengan lebih sederhana.", period_used)
    if any(v.result.error for v in votes):
        return tahan("T0", "Layanan pendukung sedang tidak dapat memberi hasil lengkap. Coba lagi.", period_used)

    def ev(v: VoteResult) -> Evidence:
        c = (candidates or {}).get(v.candidate_code) or Candidate(code=v.candidate_code, canonical_name=v.candidate_code, unit=v.result.unit)
        return Evidence(candidate=c, result=v.result)

    evidences = [ev(v) for v in votes]
    if len(votes) == 1 or all(setara(a.result, b.result, tau) for a, b in combinations(votes, 2)):    # (5): semua PASANGAN
        return Decision(decision="JAWAB", answer=evidences[0], period_used=period_used)
    return Decision(decision="TANYA", evidence=evidences, period_used=period_used)
