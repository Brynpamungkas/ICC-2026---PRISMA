"""Metrik D10 C6 (pers. 7-8, profil A K-20) dan pemeriksa jawaban. Data SYNTHETIC, dihitung tangan."""
import sys
from pathlib import Path

import pytest

from backend.app import eval_metrics as em

ROOT = Path(__file__).resolve().parents[3]


def _lab(y, group, rows=None, period="2099-01", op="NONE", codes=("X",), domain="kemiskinan"):
    return {"y": y, "group": group, "domain": domain, "indicator_codes": list(codes),
            "refs": [{"rows": rows or [["A", 1.0]], "error": None, "period": period, "operation": op}]}


def _rec(q, dec, rows=None, reason=None, period="2099-01", k=("X",), ms=10.0):
    return {"question_id": q, "decision": dec, "reason_code": reason, "answer_rows": rows, "answer_error": None,
            "period_used": period, "k": list(k), "latency_ms": ms}


def test_d10_c61_hand_example_profile_a():
    labels = {"Q1": _lab("TANYA", "AMBIGU_TEKS"), "Q2": _lab("JAWAB", "TAK_AMBIGU", rows=[["A", 1.0]]),
              "Q3": _lab("JAWAB", "TAK_AMBIGU"), "Q4": _lab("TANYA", "AMBIGU_TEKS")}
    recs = [_rec("Q1", "JAWAB", rows=[["A", 1.0]]), _rec("Q2", "JAWAB", rows=[["A", 2.0]]),   # Q2 salah
            _rec("Q3", "TANYA"), _rec("Q4", "TAHAN", reason="T4")]
    m = em.compute(recs, labels)
    assert m["TKS"]["value"] == 0.5 and m["PBT"]["value"] == 0.5
    assert m["confusion_positive_TANYA"] == {"TP": 0, "FP": 1, "FN": 2, "TN": 1}
    assert m["F1_TANYA"]["value"] == 0 and m["EX"]["num"] == 0 and m["EX"]["den"] == 2
    assert m["TAHAN_per_kode"]["T4"]["value"] == 0.25 and m["TAHAN_per_kode"]["T1"]["num"] == 0


def test_missing_record_stays_in_q_and_na_denominators():
    labels = {"Q1": _lab("TANYA", "AMBIGU_TEKS")}
    m = em.compute([], labels)
    assert m["Q"] == 1 and m["missing_records"] == ["Q1"] and m["decisions"]["tanpa_decision"]["num"] == 1
    assert m["PBT"]["value"] is None and m["PBT"]["note"].startswith("N/A")
    assert m["EX"]["value"] is None


@pytest.mark.parametrize("rows,period,ref,ok", [
    ([["Aceh", 12.34]], "2026-03", {"rows": [["aceh", 12.340000001]], "period": "2026-03", "operation": "NONE"}, True),
    ([[12.34]], "2026-03", {"rows": [["Aceh", 12.34]], "period": "2026-03", "operation": "NONE"}, True),     # nama tak wajib
    ([["Bali", 1.59]], None, {"rows": [["Papua", 1.59]], "operation": "RANK"}, False),                      # RANK: nama wajib
    ([["bali", 1.59]], None, {"rows": [["Bali", 1.59]], "operation": "RANK"}, True),
    ([["Aceh", 12.34]], "2025-09", {"rows": [["Aceh", 12.34]], "period": "2026-03", "operation": "NONE"}, False),
    ([["Aceh", "2026-03", 12.34]], "2026-03", {"rows": [["Aceh", 12.34]], "period": "2026-03"}, True),   # kolom periode
    ([["B", 2.0], ["A", 1.0]], None, {"rows": [["A", 1.0], ["B", 2.0]], "operation": "RANK"}, False),   # urutan RANK
    ([["B", 2.0], ["A", 1.0]], None, {"rows": [["A", 1.0], ["B", 2.0]], "operation": "NONE"}, True),
    ([[5.0167]], None, {"rows": [[5.016666666666667]], "operation": "AVG"}, False),                    # tanpa pembulatan
    ([["A", 1.0]], None, {"rows": [["A", 1.0]], "error": "SQL_ERROR: x"}, False),
    ([], None, {"rows": []}, False),
])
def test_answer_checker(rows, period, ref, ok):
    assert em.answer_matches(rows, period, ref) is ok


def test_quantile_linear():
    assert em.quantile([1, 2, 3, 4], 0.5) == 2.5 and em.quantile([], 0.5) is None
    assert em.quantile([10.0], 0.95) == 10.0


def test_linking_any_vs_all():
    labels = {"Q1": _lab("TANYA", "AMBIGU_TEKS", codes=("A", "B"))}
    m = em.compute([_rec("Q1", "TANYA", k=("A",))], labels)
    assert m["linking_any"]["num"] == 1 and m["linking_all"]["num"] == 0


def test_replay_changes_decision_with_tau():
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_eval
    from backend.app.catalog import get_catalog
    cat = get_catalog()
    a, b = "TPT_PERSEN", "KMS_PERSEN"                       # dua indikator satuan % (hanya untuk uji replay)

    def res(code, v):
        return {"candidate_code": code, "columns": ["nilai"], "rows": [[v]], "structure": "NUMBER", "unit": "%", "error": None}
    rec = {"question_id": "Q", "decision": "TANYA", "period_used": "2099-01",
           "log": {"k_prime": [a, b], "votes": [{"candidate_code": a, "result": res(a, 5.0), "votes": 64},
                                                {"candidate_code": b, "result": res(b, 5.3), "votes": 64}]}}
    assert run_eval.replay_k3(rec, {"%": 0.1}, cat)["decision"] == "TANYA"
    out = run_eval.replay_k3(rec, {"%": 0.5}, cat)
    assert out["decision"] == "JAWAB" and out["answer_rows"] == [[5.0]]
