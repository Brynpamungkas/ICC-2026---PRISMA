"""Langkah 6: voting vektor hasil terbanyak, persamaan (3), aturan seri K-05.
Identitas vektor = seluruh nilai, tipe, kolom, urutan baris dan urutan kandidat (bukan SQL; tanpa tau; tanpa pembulatan).
Frekuensi dihitung per SAMPEL (kerangka duplikat tetap menyumbang suara). Seri: sampel yang muncul pertama (config
decision.vote_tie_break=first_seen, USULAN K-05), dicatat pada VoteResult.tie. Satu pemenang utuh, bukan gabungan."""
from __future__ import annotations

import json

from backend.app.schemas import ExecResult, VoteResult


def _key(vector: list[ExecResult]) -> str:
    return json.dumps([[r.candidate_code, r.columns, r.rows, r.structure, r.unit, r.error] for r in vector],
                      sort_keys=True, ensure_ascii=False)


def vote(results_per_skeleton: list[list[ExecResult]]) -> list[VoteResult]:
    if not results_per_skeleton:
        return []
    counts: dict[str, int] = {}
    first_seen: dict[str, int] = {}
    vectors: dict[str, list[ExecResult]] = {}
    for i, vec in enumerate(results_per_skeleton):
        k = _key(vec)
        counts[k] = counts.get(k, 0) + 1
        first_seen.setdefault(k, i)
        vectors.setdefault(k, vec)
    top = max(counts.values())
    tied = [k for k, c in counts.items() if c == top]
    winner = min(tied, key=lambda k: first_seen[k])
    return [VoteResult(candidate_code=r.candidate_code, result=r, votes=top, tie=len(tied) > 1) for r in vectors[winner]]
