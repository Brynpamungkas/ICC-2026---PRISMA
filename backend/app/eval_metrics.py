"""Metrik evaluasi D10 C6/C7 (paper pers. 7-8) dan pemeriksa jawaban. Fungsi murni: tanpa model/DB.

Keputusan tim 20 Okt 2026 (K-20, K-17 checker), dicatat di D13:
- Profil A D10 EVAL-13: kelas positif TANYA; JAWAB/TAHAN/tanpa-Decision = negatif. EX: q tak ambigu yang tidak dijawab
  benar (TANYA/TAHAN/gagal) = 0; penyebut tetap card(U). Q tidak pernah dikurangi; N/A hanya bila penyebut 0.
- Pemeriksa jawaban (bukan fungsi setara PRISMA, tanpa tau): galat eksekusi = salah; periode jawaban harus sama dengan
  periode interpretasi rujukan bila keduanya ada; nilai baris dibandingkan sebagai multiset per baris (angka |a-b|<=1e-6,
  kolom periode YYYY-MM diabaikan karena sudah diperiksa terpisah). Untuk RANK: teks (nama provinsi) ikut dibandingkan
  (casefold) dan urutan baris diperhatikan; operasi lain: hanya angka, urutan baris bebas. Cocok dengan SALAH SATU interpretasi rujukan = benar (JAWAB dengan >1 tafsir yang setara menurut manusia).
- Latensi: kuantil interpolasi linear (tipe 7) atas durasi respons pertama seluruh pertanyaan yang berakhir dengan Decision.
"""
from __future__ import annotations

import math
import re
from collections import Counter

_PERIOD = re.compile(r"^\d{4}-\d{2}$")
REASONS = ["T0", "T1", "T2", "T3", "T4", "T5"]


def _token(v):
    if v is None:
        return ("null",)
    if isinstance(v, bool):
        return ("bool", v)
    if isinstance(v, (int, float)):
        return ("num", round(float(v), 6))
    return ("txt", str(v).strip().casefold())


def _row_key(row: list, keep_text: bool) -> list:
    """Nilai baris sebagai multiset token. Teks (nama provinsi) hanya dibandingkan untuk RANK, karena di sana nama
    adalah jawabannya; di operasi lain wilayah sudah ditetapkan pertanyaan, jadi yang dinilai angkanya."""
    toks = [_token(v) for v in row if not (isinstance(v, str) and _PERIOD.match(v.strip()))]
    return sorted(t for t in toks if keep_text or t[0] != "txt")


def _close(a: list, b: list) -> bool:
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x[0] != y[0]:
            return False
        if x[0] == "num" and abs(x[1] - y[1]) > 1e-6:
            return False
        if x[0] != "num" and x != y:
            return False
    return True


def answer_matches(rows: list[list], period_used: str | None, ref: dict) -> bool:
    """ref: {rows, error, period, operation}. True bila jawaban sistem cocok dengan satu interpretasi rujukan."""
    if ref.get("error"):
        return False
    if ref.get("period") and period_used and ref["period"] != period_used:
        return False
    rank = (ref.get("operation") or "").upper().startswith("RANK")
    sys_rows = [_row_key(r, keep_text=rank) for r in rows]
    ref_rows = [_row_key(r, keep_text=rank) for r in ref.get("rows", [])]
    if len(sys_rows) != len(ref_rows) or not ref_rows:
        return False
    if not rank:
        sys_rows, ref_rows = sorted(sys_rows), sorted(ref_rows)
    return all(_close(a, b) for a, b in zip(sys_rows, ref_rows))


def is_correct(rec: dict, label: dict) -> bool:
    if rec.get("decision") != "JAWAB" or rec.get("answer_error"):
        return False
    return any(answer_matches(rec.get("answer_rows") or [], rec.get("period_used"), ref) for ref in label["refs"])


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    h = (len(xs) - 1) * q
    lo, hi = math.floor(h), math.ceil(h)
    return xs[lo] + (xs[hi] - xs[lo]) * (h - lo)


def _ratio(num: int, den: int) -> dict:
    return {"num": num, "den": den, "value": (num / den) if den else None, "note": None if den else "N/A: penyebut 0"}


def compute(records: list[dict], labels: dict[str, dict]) -> dict:
    """records: satu per question_id (decision None = tanpa Decision). labels: question_id -> {y, group, domain, refs,
    indicator_codes}. Pertanyaan berlabel tanpa record dihitung sebagai tanpa Decision (Q tidak dikurangi)."""
    by_q = {r["question_id"]: r for r in records}
    Q = sorted(labels)
    missing_records = [q for q in Q if q not in by_q]
    dec = {q: (by_q.get(q) or {}).get("decision") for q in Q}
    y = {q: labels[q]["y"] for q in Q}
    correct = {q: is_correct(by_q[q], labels[q]) if q in by_q else False for q in Q}

    tks_num = sum(1 for q in Q if dec[q] == "JAWAB" and (y[q] == "TANYA" or not correct[q]))
    y_jawab = [q for q in Q if y[q] == "JAWAB"]
    pbt_num = sum(1 for q in y_jawab if dec[q] == "TANYA")
    tp = sum(1 for q in Q if dec[q] == "TANYA" and y[q] == "TANYA")
    fp = sum(1 for q in Q if dec[q] == "TANYA" and y[q] == "JAWAB")
    fn = sum(1 for q in Q if dec[q] != "TANYA" and y[q] == "TANYA")
    tn = sum(1 for q in Q if dec[q] != "TANYA" and y[q] == "JAWAB")
    U = [q for q in Q if labels[q]["group"] == "TAK_AMBIGU"]
    ex_num = sum(1 for q in U if correct[q])
    link_any = sum(1 for q in Q if set(labels[q]["indicator_codes"]) & set((by_q.get(q) or {}).get("k") or []))
    link_all = sum(1 for q in Q if labels[q]["indicator_codes"]
                   and set(labels[q]["indicator_codes"]) <= set((by_q.get(q) or {}).get("k") or []))
    reasons = Counter((by_q[q].get("reason_code") for q in Q if q in by_q and dec[q] == "TAHAN"))
    lat = [by_q[q]["latency_ms"] for q in Q if q in by_q and dec[q] is not None and by_q[q].get("latency_ms") is not None]
    n = len(Q)
    return {
        "Q": n, "U": len(U), "y_JAWAB": len(y_jawab), "y_TANYA": n - len(y_jawab),
        "missing_records": missing_records,
        "TKS": _ratio(tks_num, n),
        "PBT": _ratio(pbt_num, len(y_jawab)),
        "precision_TANYA": _ratio(tp, tp + fp),
        "recall_TANYA": _ratio(tp, tp + fn),
        "F1_TANYA": _ratio(2 * tp, 2 * tp + fp + fn),
        "confusion_positive_TANYA": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
        "EX": _ratio(ex_num, len(U)),
        "linking_any": _ratio(link_any, n),
        "linking_all": _ratio(link_all, n),
        "decisions": {k: _ratio(sum(1 for q in Q if dec[q] == k), n) for k in ("JAWAB", "TANYA", "TAHAN")}
        | {"tanpa_decision": _ratio(sum(1 for q in Q if dec[q] is None), n)},
        "TAHAN_per_kode": {c: _ratio(reasons.get(c, 0), n) for c in REASONS},
        "latency_ms": {"n": len(lat), "p50": quantile(lat, 0.5), "p95": quantile(lat, 0.95)},
    }


def compute_breakdown(records: list[dict], labels: dict[str, dict]) -> dict:
    out = {"semua": compute(records, labels)}
    for key in ("group", "domain"):
        for val in sorted({lab[key] for lab in labels.values()}):
            sub = {q: lab for q, lab in labels.items() if lab[key] == val}
            out[f"{key}={val}"] = compute([r for r in records if r["question_id"] in sub], sub)
    return out
