"""Tes alur lengkap M2: DB hasil ETL dari data BPS ASLI + klien TIRUAN (hanya menyuplai kerangka SQL; BUKAN bukti kinerja model,
bukan hasil evaluasi). Tiga kasus Tabel A-4 diuji di sini; tes emas FROZEN di backend/tests/golden tetap menunggu model nyata (M3)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import etl  # noqa: E402

from backend.app.config import ConfigError  # noqa: E402
from backend.app.llm.client import LlmClient, LlmUnavailable  # noqa: E402
from backend.app.llm.mock import MockLlmClient  # noqa: E402
from backend.app.orchestrator import clarify, run_question, run_question_with_log  # noqa: E402

RANK = ("SELECT p.nama AS wilayah, n.nilai AS nilai FROM nilai_indikator n JOIN provinsi p ON p.kode=n.kode_provinsi "
        "WHERE n.kode_indikator=:indikator AND n.periode=:periode ORDER BY n.nilai DESC LIMIT 1")
SUM6 = ("SELECT SUM(n.nilai) AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:indikator AND n.periode=:periode "
        "AND n.kode_provinsi IN (:wilayah_0,:wilayah_1,:wilayah_2,:wilayah_3,:wilayah_4,:wilayah_5)")
ONE = ("SELECT n.nilai AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:indikator AND n.periode=:periode "
       "AND n.kode_provinsi = :wilayah_0")
ONE_W = ("SELECT p.nama AS wilayah, n.nilai AS nilai FROM nilai_indikator n JOIN provinsi p ON p.kode=n.kode_provinsi "
         "WHERE n.kode_indikator=:indikator AND n.periode=:periode AND n.kode_provinsi = :wilayah_0")   # bentuk prompt v0.2.3
EMPTY = ("SELECT n.nilai AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:indikator AND n.nilai > 1e12 "
         "ORDER BY n.nilai DESC LIMIT 1")      # bentuk RANK (validator menegakkan bentuk S1 sejak 21 Okt)
TAU = {"%": 0.0, "ribu jiwa": 0.0, "orang": 0.0}     # hanya agar tes berjalan; kalibrasi sungguhan = M5


class CountingLlm(MockLlmClient):
    calls = 0

    def generate(self, prompt, n):
        type(self).calls += 1
        return super().generate(prompt, n)


class DownLlm:
    def generate(self, prompt, n):
        raise LlmUnavailable("down")


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    d = tmp_path_factory.mktemp("db")
    assert etl.build(False, etl.RAW_DIR / "manifest.yaml", d / "p.sqlite", d / "r.json") == 0
    return d / "p.sqlite"


def ask(q, sql, db, **kw):
    return run_question_with_log(q, llm=MockLlmClient([sql] if isinstance(sql, str) else sql), db_path=db, tau=TAU, **kw)


def test_gold01_tanya_with_two_official_answers(db):
    d, rec = ask("Provinsi mana yang paling miskin?", RANK, db)
    assert d.decision == "TANYA" and d.period_used == "2025-09"
    got = {e.candidate.code: e.result.rows for e in d.evidence}
    assert got == {"KMS_PERSEN": [["Papua Tengah", 29.45]], "KMS_JUMLAH": [["Jawa Timur", 3804.29]]}      # paper III-D
    assert rec.votes[0].votes == 64


def test_gold02_jawab_percent_dropped_by_sigma(db):
    d, rec = ask("Berapa total penduduk miskin di Pulau Jawa?", SUM6, db)
    assert d.decision == "JAWAB" and d.answer.candidate.code == "KMS_JUMLAH" and d.period_used == "2025-09"
    assert d.answer.result.rows == [[12322.58]] or abs(d.answer.result.rows[0][0] - 12322.58) < 1e-6
    assert rec.k == ["KMS_PERSEN", "KMS_JUMLAH"] and rec.k_prime == ["KMS_JUMLAH"]


def test_gold03_tahan_t1_without_calling_model(db):
    CountingLlm.calls = 0
    d, rec = run_question_with_log("Berapa IPM Jawa Barat?", llm=CountingLlm([RANK]), db_path=db, tau=TAU)
    assert (d.decision, d.reason_code) == ("TAHAN", "T1") and d.suggestion
    assert CountingLlm.calls == 0 and set(rec.latency_ms) == {"s1", "s2"}          # langkah dilewati tidak dicatat 0 ms


def test_abbreviation_questions_resolve_after_kamus_fix(db):
    d, rec = ask("TPT Bali", ONE, db)
    assert rec.k == ["TPT_PERSEN"] and d.decision == "JAWAB"
    d, rec = ask("APM SMA Aceh", ONE, db)
    assert rec.k == ["APM_SMA"] and d.decision == "JAWAB"


def test_unknown_place_is_t2_not_all_provinces(db):
    d, _ = ask("kemiskinan di Bandung", RANK, db)          # kota, bukan provinsi ("jakarta" kini alias DKI Jakarta)
    assert (d.decision, d.reason_code) == ("TAHAN", "T2") and "bandung" in d.suggestion.lower()


def test_explicit_unavailable_period_is_t2_and_not_replaced(db):
    d, _ = ask("persentase penduduk miskin di Papua tahun 2030", ONE, db)
    assert d.reason_code == "T2" and "2030" in d.suggestion


def test_t3_sum_of_percent(db):
    d, _ = ask("total persentase penduduk miskin di Pulau Jawa", SUM6, db)
    assert d.reason_code == "T3"


def test_t4_when_no_valid_skeleton(db):
    d, rec = ask("Provinsi mana yang paling miskin?", "DROP TABLE provinsi", db)
    assert d.reason_code == "T4" and len(rec.skeletons) == 64 and not any(s.valid for s in rec.skeletons)


def test_partial_invalid_skeletons_keep_original_indexes(db):
    d, rec = ask("Provinsi mana yang paling miskin?", [RANK, "DROP TABLE provinsi"], db)
    assert d.decision == "TANYA" and rec.votes[0].votes == 32 and sum(s.valid for s in rec.skeletons) == 32


def test_t5_all_results_empty_before_voting(db):
    d, rec = ask("Provinsi mana yang paling miskin?", EMPTY, db)
    assert d.reason_code == "T5" and rec.votes == []


def test_model_or_db_failure_is_tahan_not_raw_error(db, tmp_path):
    d = run_question("Provinsi mana yang paling miskin?", llm=DownLlm(), db_path=db, tau=TAU)
    assert (d.decision, d.reason_code) == ("TAHAN", "T0")                         # nama kode: K-06 OPEN
    d = run_question("Provinsi mana yang paling miskin?", llm=MockLlmClient([RANK]), db_path=tmp_path / "none.sqlite", tau=TAU)
    assert (d.decision, d.reason_code) == ("TAHAN", "T0")


def test_clarify_uses_stored_evidence_without_model(db):
    d, _ = ask("Provinsi mana yang paling miskin?", RANK, db)
    j = clarify(d, "KMS_PERSEN")
    assert j.decision == "JAWAB" and j.answer.result.rows == [["Papua Tengah", 29.45]]
    with pytest.raises(ValueError):
        clarify(d, "TPT_PERSEN")


def test_k1_k2_not_implemented_yet():
    with pytest.raises(NotImplementedError):
        run_question("x", "K2")


def test_numeric_equal_units_need_calibrated_tau(db):
    """Pendidikan: tiga ukuran persen -> perbandingan numerik memerlukan tau; null = galat, bukan nilai bawaan."""
    with pytest.raises(ConfigError):
        run_question("partisipasi sekolah di Aceh", llm=MockLlmClient([ONE]), db_path=db, tau={"%": None})
    d = run_question("partisipasi sekolah di Aceh", llm=MockLlmClient([ONE]), db_path=db, tau={"%": 100.0})
    assert d.decision == "JAWAB"          # semua selisih <= tau fiktif 100: hanya membuktikan jalur numerik, bukan nilai tau


def test_jsonl_log_one_line_per_question(db, tmp_path):
    log = tmp_path / "log.jsonl"
    ask("Provinsi mana yang paling miskin?", RANK, db, log_path=str(log), session_id="s1")
    ask("Berapa IPM Jawa Barat?", RANK, db, log_path=str(log), session_id="s1")
    lines = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2 and lines[0]["decision"]["decision"] == "TANYA" and lines[1]["decision"]["reason_code"] == "T1"
    assert lines[0]["dictionary_hash"] and len(lines[0]["skeletons"]) == 64


def test_llm_client_vllm_payload_and_failures(monkeypatch):
    seen = {}

    class R:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": "a"}}, {"message": {"content": "b"}}]}

    def fake_post(url, json=None, timeout=None):
        seen.update(url=url, payload=json)
        return R()

    import backend.app.llm.client as mod
    monkeypatch.setattr(mod.requests, "post", fake_post)
    out = LlmClient().generate("p", 64)
    assert out == ["a", "b"]                                                     # < n diterima apa adanya (EDGE-34)
    assert seen["payload"]["n"] == 64 and seen["payload"]["seed"] is not None

    def boom(*a, **k):
        raise mod.requests.ConnectionError("x")

    monkeypatch.setattr(mod.requests, "post", boom)
    with pytest.raises(LlmUnavailable):
        LlmClient().generate("p", 4)


def test_lookup_with_region_label_column_compares_numbers_not_names(db):
    """Perbaikan 21 Okt (Tabel VII): kolom wilayah pada pencarian nilai hanya label; persen vs ribu jiwa -> TANYA, bukan JAWAB."""
    d, _ = ask("Kemiskinan di Gorontalo pada Maret 2025?", ONE_W, db)
    assert d.decision == "TANYA" and {e.candidate.code for e in d.evidence} == {"KMS_PERSEN", "KMS_JUMLAH"}
    assert all(e.result.structure == "NUMBER" for e in d.evidence)
    d, _ = ask("Persentase penduduk miskin di Gorontalo pada Maret 2025?", ONE_W, db)
    assert d.decision == "JAWAB" and d.answer.result.rows[0][0] == "Gorontalo"


def test_validator_enforces_s1_shape_so_wrong_rank_direction_cannot_win(db):
    """21 Okt: model menulis SUM ... ORDER BY DESC LIMIT 1 untuk "paling tidak miskin"; kini ditolak, kerangka benar menang."""
    wrong = ("SELECT p.nama AS wilayah, SUM(n.nilai) AS nilai FROM nilai_indikator n JOIN provinsi p ON p.kode=n.kode_provinsi "
             "WHERE n.kode_indikator=:indikator AND n.periode=:periode AND n.kode_provinsi IN (:wilayah_0, :wilayah_1) "
             "GROUP BY p.nama ORDER BY nilai DESC LIMIT 1")
    right = ("SELECT p.nama AS wilayah, n.nilai AS nilai FROM nilai_indikator n JOIN provinsi p ON p.kode=n.kode_provinsi "
             "WHERE n.kode_indikator=:indikator AND n.periode=:periode AND n.kode_provinsi IN (:wilayah_0, :wilayah_1) "
             "ORDER BY nilai ASC LIMIT 1")
    d, rec = ask("Mana yang paling tidak miskin, Bali atau Banten?", [wrong, wrong, wrong, right], db)
    assert sum(s.valid for s in rec.skeletons) == 16 and d.decision == "JAWAB" and d.answer.result.rows[0][0] == "Bali"
