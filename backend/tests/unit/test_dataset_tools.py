"""scripts/dataset_tools.py: komposisi Tabel VIII, kappa D11 ANN-10, split Hamilton D10 EVAL-07. Data SYNTHETIC."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import dataset_tools as T  # noqa: E402


def _questions():
    rows, i = [], 0
    for (g, d), n in T.COMPOSITION.items():
        for _ in range(n):
            i += 1
            rows.append({"question_id": f"SYN-{i:03d}", "domain": d, "target_group": g,
                         "source_kind": "mahasiswa" if i <= 60 else "tim", "source_record_id": "S",
                         "author": "x", "question_text": f"pertanyaan SYNTHETIC nomor {i}"})
    return rows


def test_full_composition_passes():
    errs, stats = T.check_questions(_questions())
    assert errs == [] and T.composition_complete(stats)


def test_swapped_cells_rejected_even_with_correct_totals():
    rows = _questions()
    a = next(r for r in rows if r["target_group"] == "TAK_AMBIGU" and r["domain"] == "kemiskinan")
    b = next(r for r in rows if r["target_group"] == "AMBIGU_ANGKA_SAMA" and r["domain"] == "pendidikan")
    a["target_group"], b["target_group"] = "AMBIGU_ANGKA_SAMA", "TAK_AMBIGU"   # total baris/kolom tetap, dua sel tertukar
    errs, stats = T.check_questions(rows)
    assert errs == [] and stats["total"] == [180, 180] and not T.composition_complete(stats)


def test_probe_and_duplicate_questions_rejected():
    rows = _questions()[:2]
    rows[0]["question_text"] = "Berapa persentase penduduk miskin di Aceh?"
    rows[1]["question_text"] = "berapa persentase penduduk miskin di aceh"
    errs, _ = T.check_questions(rows)
    assert any("probe" in e for e in errs) and any("teks sama" in e for e in errs)


def test_kappa_matches_hand_computation():
    # A: J J J T T ; B: J J T T T  -> Po=0.8; pA(J)=0.6 pB(J)=0.4 -> Pe=0.24+0.24=0.48; k=0.32/0.52
    a = dict(zip("abcde", ["JAWAB", "JAWAB", "JAWAB", "TANYA", "TANYA"]))
    b = dict(zip("abcde", ["JAWAB", "JAWAB", "TANYA", "TANYA", "TANYA"]))
    rep = T.cohen_kappa(a, b)
    assert rep["N"] == 5 and rep["Po"] == pytest.approx(0.8) and rep["Pe"] == pytest.approx(0.48)
    assert rep["kappa"] == pytest.approx(0.32 / 0.52)


def test_kappa_na_cases():
    assert T.cohen_kappa({}, {})["kappa"] is None
    same = {"a": "JAWAB", "b": "JAWAB"}
    rep = T.cohen_kappa(same, same)
    assert rep["kappa"] is None and "Pe=1" in rep["note"]                 # bukan kappa=1 otomatis


def test_hamilton_reproduces_d10_dev_table():
    q = T.hamilton_quotas(dict(T.COMPOSITION), 0.30)
    assert sum(q.values()) == 54
    assert q[("TAK_AMBIGU", "pendidikan")] == 5 and q[("AMBIGU_TEKS", "pendidikan")] == 4
    assert q[("AMBIGU_ANGKA_SAMA", "pendidikan")] == 9 and q[("AMBIGU_ANGKA_BEDA", "kemiskinan")] == 6


def test_split_deterministic_disjoint_and_seed_dependent():
    cells = {("TAK_AMBIGU", "kemiskinan"): [f"Q{i}" for i in range(20)]}
    quotas = {("TAK_AMBIGU", "kemiskinan"): 6}
    d1, t1 = T.split_ids(cells, quotas, "s1")
    d2, _ = T.split_ids(cells, quotas, "s1")
    d3, _ = T.split_ids(cells, quotas, "s2")
    assert d1 == d2 and len(d1) == 6 and not set(d1) & set(t1) and len(d1) + len(t1) == 20
    assert d1 != d3


def test_label_rules():
    base = {"question_id": "Q1", "annotator_id": "A", "question_group": "AMBIGU_TEKS", "decision_reference": "TANYA",
            "interpretation_id": "I1", "meaning": "m", "indicator_code": "KMS_PERSEN", "region_codes": "",
            "period": "2025-09", "operation": "RANK", "reference_sql": "SELECT 1", "rationale": "r",
            "uncertainty_notes": "tidak ada", "source_refs": "x", "verification_status": "DRAFT"}
    errs = T.check_labels([base], {"Q1"}, {"KMS_PERSEN"})
    assert any("minimal dua" in e for e in errs)                        # TANYA perlu >=2 interpretasi
    errs = T.check_labels([{**base, "decision_reference": "TAHAN"}], {"Q1"}, {"KMS_PERSEN"})
    assert any("TAHAN bukan label utama" in e for e in errs)


def _lrow(qid, iid, code, op, period="", regions="", sql=""):
    return {"question_id": qid, "annotator_id": "A", "question_group": "AMBIGU_TEKS", "decision_reference": "TANYA",
            "interpretation_id": iid, "meaning": "m", "indicator_code": code, "region_codes": regions, "period": period,
            "operation": op, "reference_sql": sql, "rationale": "r", "uncertainty_notes": "", "source_refs": "x",
            "verification_status": "DRAFT"}


def test_buat_sql_uses_common_latest_period_and_executes(tmp_path):
    from backend.app.catalog import get_catalog
    import etl
    db = tmp_path / "p.sqlite"
    assert etl.build(False, etl.RAW_DIR / "manifest.yaml", db, tmp_path / "r.json") == 0
    rows = [_lrow("Q1", "I1", "KMS_PERSEN", "RANK_DESC_1"), _lrow("Q1", "I2", "KMS_JUMLAH", "RANK_DESC_1")]
    filled, notes = T.fill_reference_sql(rows, get_catalog())
    assert notes == [] and {r["period"] for r in filled} == {"2025-09"}               # terbaru bersama, paper III-C
    assert all("otomatis" in r["uncertainty_notes"] for r in filled)
    ans = {a["interpretation_id"]: a["rows"] for a in T.execute_reference(filled, db)}
    assert ans == {"I1": [["Papua Tengah", 29.45]], "I2": [["Jawa Timur", 3804.29]]}  # sama dengan uji GOLD-01


def test_buat_sql_rejects_sum_of_percent_and_bad_inputs():
    from backend.app.catalog import get_catalog
    cat = get_catalog()
    _, notes = T.fill_reference_sql([_lrow("Q", "I1", "KMS_PERSEN", "SUM", "2025-09", "31;32")], cat)
    assert any("SUM atas persen" in n for n in notes)
    _, notes = T.fill_reference_sql([_lrow("Q", "I1", "KMS_JUMLAH", "NONE", "2026-03")], cat)
    assert any("tidak tersedia" in n for n in notes)
    _, notes = T.fill_reference_sql([_lrow("Q", "I1", "KMS_JUMLAH", "NONE", "2025-09", "99")], cat)
    assert any("provinsi" in n for n in notes)


def test_existing_sql_is_never_overwritten():
    from backend.app.catalog import get_catalog
    filled, _ = T.fill_reference_sql([_lrow("Q", "I1", "KMS_JUMLAH", "NONE", "2025-09", sql="SELECT 42")], get_catalog())
    assert filled[0]["reference_sql"] == "SELECT 42"


def test_operation_format_validated():
    errs = T.check_labels([_lrow("Q", "I1", "KMS_PERSEN", "RANK", "2025-09", sql="SELECT 1"),
                           _lrow("Q", "I2", "KMS_JUMLAH", "RANK_DESC_1", "2025-09", sql="SELECT 1")],
                          {"Q"}, {"KMS_PERSEN", "KMS_JUMLAH"})
    assert any("RANK_DESC_k" in e for e in errs) and sum("operation" in e for e in errs) == 1


def test_llm_source_allowed_and_student_count_is_reported_not_blocking():
    rows = [dict(r, source_kind="llm") for r in _questions()]
    errs, stats = T.check_questions(rows)
    assert errs == [] and T.composition_complete(stats) and stats["mahasiswa"] == [0, 60]


def test_split_before_labels_uses_target_group_and_matches_d10_quotas(tmp_path):
    qs = _questions()
    path = tmp_path / "q.csv"
    T.write_csv(path, qs, T.Q_COLS)
    out = T.ROOT / "eval" / "testset" / "split_seed-uji_sintetis.json"
    try:
        assert T.main(["split", str(path), "--seed", "uji sintetis"]) == 0
        import json
        s = json.loads(out.read_text(encoding="utf-8"))
        assert len(s["dev"]) == 54 and len(s["test"]) == 126 and s["strata"] == "target_group penyusun"
        lab = tmp_path / "l.csv"
        T.write_csv(lab, [{"question_id": q, "annotator_id": "FINAL", "verification_status": "VERIFIED"} for q in s["dev"]]
                    + [{"question_id": q, "annotator_id": "FINAL", "verification_status": "DRAFT"} for q in s["test"]], T.L_COLS)
        assert T.main(["cek-cakupan", str(out), str(lab), "--bagian", "dev"]) == 0
        assert T.main(["cek-cakupan", str(out), str(lab), "--bagian", "test"]) == 1
    finally:
        out.unlink(missing_ok=True)


def test_correction_report_counts_only_verified_and_detects_changes():
    d = [_lrow("Q1", "I1", "KMS_PERSEN", "NONE", "2025-09", "11"), _lrow("Q2", "I1", "TPT_PERSEN", "NONE", "", "51"),
         _lrow("Q3", "I1", "APM_SD", "NONE", "", "32")]
    f = [dict(r, verification_status="VERIFIED") for r in d]
    f[1] = dict(f[1], indicator_code="PGR_JUMLAH")                                       # Q2 diubah verifikator
    f[2] = dict(f[2], verification_status="DRAFT")                                       # Q3 belum diperiksa
    rep = T.correction_report(d, f)
    assert rep["verified_questions"] == 2 and rep["unverified"] == ["Q3"]
    assert rep["changed_any"]["ids"] == ["Q2"] and rep["changed_any"]["value"] == 0.5
    assert rep["changed_decision"]["num"] == 0
