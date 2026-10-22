"""Tes M2 langkah 1-3 dan 5-7 + sqlguard. Semua data di sini SYNTHETIC (bukan data BPS, bukan hasil evaluasi)."""
import copy
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import catalog_lib  # noqa: E402

from backend.app.catalog import Catalog, IndicatorMeta  # noqa: E402
from backend.app.config import ConfigError, load_config  # noqa: E402
from backend.app.schemas import ExecResult, ExtractionResult, VoteResult  # noqa: E402
from backend.app.sqlguard.executor import DatabaseUnavailable, run_query  # noqa: E402
from backend.app.sqlguard.validator import validate_sql  # noqa: E402
from backend.app.steps.s1_extract import extract  # noqa: E402
from backend.app.steps.s2_resolve import resolve  # noqa: E402
from backend.app.steps.s3_checks import check_candidates  # noqa: E402
from backend.app.steps.s6_vote import vote  # noqa: E402
from backend.app.steps.s7_decide import decide, setara  # noqa: E402
from backend.app.text import normalize_term  # noqa: E402


@pytest.fixture
def cat():
    ind = {
        "A_PCT": IndicatorMeta("A_PCT", "Ukuran A Persen", "d", "%", "SYN", frozenset({"01", "02"}), frozenset({"2025-03", "2025-09"})),
        "A_NUM": IndicatorMeta("A_NUM", "Jumlah Ukuran A", "d", "orang", "SYN", frozenset({"01", "02"}), frozenset({"2025-03"})),
    }
    c = Catalog(indicators=ind, provinces={"01": "Alfa", "02": "Beta", "03": "Gamma"})
    c.kamus = {
        ("ukuran", "a"): {"indikator": {"A_PCT", "A_NUM"}},
        ("ukuran", "a", "persen"): {"indikator": {"A_PCT"}},
        ("jumlah", "ukuran", "a"): {"indikator": {"A_NUM"}},
        ("alfa",): {"wilayah": {"01"}},
        ("alfa", "beta"): {"wilayah": {"01", "02"}},
        ("beta",): {"wilayah": {"02"}},
        ("gamma",): {"wilayah": {"03"}},
    }
    c.operations = {("total",): "SUM", ("jumlah",): "SUM", ("rata", "rata"): "AVG"}
    return c


@pytest.fixture
def cfg():
    return load_config()


# ---------- text ----------
def test_normalization_matches_catalog_lib():
    for s in ["Rata-rata  APK SMP", "DKI Jakarta!", "angka (APM) 7-12 Tahun", "persentase 50%"]:
        assert normalize_term(s) == catalog_lib.normalize_term(s)


# ---------- S1 ----------
def test_s1_suppresses_covered_terms_only_when_configured(cat, cfg):
    e = extract("ukuran a persen di alfa", catalog=cat, config=cfg)
    assert e.terms == ["ukuran a persen"]
    cfg2 = copy.deepcopy(cfg)
    cfg2["extraction"]["suppress_covered_terms"] = False
    assert set(extract("ukuran a persen di alfa", catalog=cat, config=cfg2).terms) == {"ukuran a", "ukuran a persen"}


def test_s1_region_alias_one_to_many_and_covered_region(cat, cfg):
    assert extract("ukuran a di alfa beta", catalog=cat, config=cfg).regions == ["01", "02"]   # "alfa" tertutup "alfa beta"? tidak: kode sama
    assert extract("ukuran a di beta", catalog=cat, config=cfg).regions == ["02"]


def test_s1_jumlah_in_indicator_name_is_not_sum(cat, cfg):          # EDGE-08 / K-02
    assert extract("berapa jumlah ukuran a di alfa", catalog=cat, config=cfg).operation == "NONE"
    assert extract("berapa total ukuran a di alfa", catalog=cat, config=cfg).operation == "SUM"
    assert extract("rata-rata ukuran a di alfa", catalog=cat, config=cfg).operation == "AVG"


def test_s1_rank_direction_and_top_n(cat, cfg):
    e = extract("3 provinsi dengan ukuran a tertinggi", catalog=cat, config=cfg)
    assert (e.operation, e.rank_direction, e.top_n) == ("RANK", "highest", 3)
    e = extract("provinsi dengan ukuran a paling rendah", catalog=cat, config=cfg)
    assert (e.operation, e.rank_direction) == ("RANK", "lowest")


def test_s1_period_formats_and_no_invented_month(cat, cfg):
    assert extract("ukuran a september 2025", catalog=cat, config=cfg).period == "2025-09"
    assert extract("ukuran a 2025-03", catalog=cat, config=cfg).period == "2025-03"
    e = extract("ukuran a tahun 2026", catalog=cat, config=cfg)
    assert e.period == "2026" and e.unresolved == []                  # tahun saja: tidak mengarang bulan (K-18)
    assert extract("ukuran a september", catalog=cat, config=cfg).unresolved == ["bulan september tanpa tahun"]


def test_s1_unknown_place_is_unresolved_not_all_provinces(cat, cfg):
    e = extract("ukuran a di jakarta", catalog=cat, config=cfg)
    assert e.regions == [] and e.unresolved == ["jakarta"]
    assert extract("ukuran a di alfa", catalog=cat, config=cfg).unresolved == []


# ---------- S2 ----------
def test_s2_union_deduplicated_in_catalog_order(cat, cfg):
    e = extract("ukuran a di alfa", catalog=cat, config=cfg)
    assert [c.code for c in resolve(e, catalog=cat)] == ["A_PCT", "A_NUM"]
    assert resolve(extract("ipm di alfa", catalog=cat, config=cfg), catalog=cat) == []        # EDGE-01


# ---------- S3 ----------
def _ext(**kw):
    base = dict(raw_question="q", terms=["ukuran a"], regions=[], period=None, operation="NONE")
    base.update(kw)
    return ExtractionResult(**base)


def test_s3_default_period_is_latest_common(cat, cfg):
    k = resolve(_ext(), catalog=cat)
    out = check_candidates(_ext(), k, catalog=cat, config=cfg)
    assert out.period == "2025-03" and [c.code for c in out.k_prime] == ["A_PCT", "A_NUM"]


def test_s3_explicit_period_never_replaced(cat, cfg):                 # EDGE-04
    k = resolve(_ext(), catalog=cat)
    out = check_candidates(_ext(period="2099-01"), k, catalog=cat, config=cfg)
    assert out.k_prime == [] and out.reason == "T2" and out.period == "2099-01"


def test_s3_sum_of_percent_fails_sigma_but_other_candidate_remains(cat, cfg):
    k = resolve(_ext(operation="SUM"), catalog=cat)
    out = check_candidates(_ext(operation="SUM"), k, catalog=cat, config=cfg)
    assert [c.code for c in out.k_prime] == ["A_NUM"] and out.reason is None


def test_s3_t3_only_when_all_fail_by_sigma(cat, cfg):
    e = _ext(terms=["ukuran a persen"], operation="SUM")
    out = check_candidates(e, resolve(e, catalog=cat), catalog=cat, config=cfg)
    assert out.reason == "T3"


def test_s3_region_not_covered_gives_t2(cat, cfg):                    # EDGE-06
    e = _ext(regions=["03"])
    assert check_candidates(e, resolve(e, catalog=cat), catalog=cat, config=cfg).reason == "T2"


def test_s3_unresolved_mention_gives_t2(cat, cfg):
    e = _ext(unresolved=["jakarta"])
    assert check_candidates(e, resolve(e, catalog=cat), catalog=cat, config=cfg).reason == "T2"


# ---------- sqlguard validator ----------
GOOD = "SELECT p.nama AS wilayah, n.nilai AS nilai FROM nilai_indikator n JOIN provinsi p ON p.kode=n.kode_provinsi WHERE n.kode_indikator=:indikator AND n.periode=:periode ORDER BY n.nilai DESC LIMIT 1"


@pytest.mark.parametrize("sql,ok", [
    (GOOD, True),
    (GOOD + ";", True),
    ("SELECT SUM(n.nilai) AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:indikator AND n.kode_provinsi IN (:wilayah_0,:wilayah_1)", True),
    ("SELECT ':indikator' AS nilai", False),                                              # EDGE-39
    ("DROP TABLE provinsi", False),
    ("SELECT 1; DROP TABLE provinsi", False),
    ("PRAGMA table_info(provinsi)", False),
    ("ATTACH DATABASE 'x' AS y", False),
    ("SELECT n.nilai AS nilai FROM kamus_istilah n WHERE n.kode=:indikator", False),
    ("SELECT sqlite_version() AS nilai FROM provinsi WHERE :indikator=1", False),
    ("SELECT ROUND(n.nilai) AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:indikator", False),
    ("SELECT n.nilai AS hasil FROM nilai_indikator n WHERE n.kode_indikator=:indikator", False),
    ("SELECT * FROM nilai_indikator WHERE kode_indikator=:indikator", False),
    ("SELECT n.nilai AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:kode", False),
    ("SELECT n.nilai AS nilai FROM nilai_indikator n WHERE n.kode_indikator='KMS_PERSEN' AND :indikator=:indikator", False),
    ("SELEC nope", False),
])
def test_validator(sql, ok):
    assert validate_sql(sql, forbidden_literals={"KMS_PERSEN"})[0] is ok


# ---------- executor ----------
@pytest.fixture
def small_db(tmp_path):
    p = tmp_path / "t.sqlite"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE t (x REAL)")
    c.executemany("INSERT INTO t VALUES (?)", [(1,), (2,), (3,)])
    c.commit()
    c.close()
    return p


def test_executor_readonly_truncation_timeout(small_db):
    assert run_query("SELECT x FROM t", {}, db_path=small_db).rows == [[1.0], [2.0], [3.0]]
    assert run_query("SELECT x FROM t", {}, db_path=small_db, max_rows=3).error is None          # tepat batas != terpotong
    r = run_query("SELECT x FROM t", {}, db_path=small_db, max_rows=2)
    assert r.error == "TRUNCATED" and len(r.rows) == 2
    assert run_query("INSERT INTO t VALUES (9)", {}, db_path=small_db).error.startswith("SQL_ERROR")
    slow = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT count(*) FROM c"
    assert run_query(slow, {}, db_path=small_db, timeout_s=0.2).error == "TIMEOUT"
    with pytest.raises(DatabaseUnavailable):
        run_query("SELECT 1", {}, db_path=small_db.parent / "none.sqlite")


# ---------- S6 vote ----------
def _vec(*vals, unit="%", cols=("wilayah", "nilai")):
    return [ExecResult(candidate_code=f"C{i}", columns=list(cols), rows=[list(v)], structure="TEXT", unit=unit)
            for i, v in enumerate(vals)]


def test_s6_frequency_per_sample_and_whole_vector(cfg):
    A, B = _vec(("X", 1.0), ("Y", 2.0)), _vec(("X", 9.0), ("Y", 2.0))
    out = vote([A] * 20 + [A] * 20 + [B] * 24)                         # EDGE-21: SQL berbeda, vektor sama
    assert [v.votes for v in out] == [40, 40] and not out[0].tie
    assert out[0].result.rows == [["X", 1.0]]                          # satu pemenang utuh


def test_s6_tie_first_seen_is_recorded(cfg):
    A, B = _vec(("X", 1.0)), _vec(("Z", 1.0))
    out = vote([B, A, B, A])                                           # EDGE-19
    assert out[0].tie and out[0].result.rows == [["Z", 1.0]]


def test_s6_near_equal_vectors_not_merged_by_tau():                    # EDGE-38
    A, B = _vec(("X", 10.0)), _vec(("X", 10.01))
    out = vote([A, A, B])
    assert out[0].votes == 2


# ---------- S7 ----------
def _vote(code, rows, unit="%", structure="NUMBER", cols=("nilai",), error=None):
    return VoteResult(candidate_code=code, votes=10, result=ExecResult(
        candidate_code=code, columns=list(cols), rows=rows, structure=structure, unit=unit, error=error))


TAU = {"%": 0.5, "orang": 0.5}                                          # SYNTHETIC, bukan hasil kalibrasi


def test_s7_single_candidate_answers():                                  # EDGE-25
    assert decide([_vote("A", [[1.0]])], TAU).decision == "JAWAB"


def test_s7_text_columns_equal_answers_and_order_matters():             # EDGE-23, EDGE-30
    t = dict(structure="TEXT", cols=("wilayah", "nilai"))
    assert decide([_vote("A", [["X", 1.0], ["Y", 2.0]], **t), _vote("B", [["X", 5.0], ["Y", 9.0]], **t)], TAU).decision == "JAWAB"   # EDGE-31
    assert decide([_vote("A", [["X", 1.0], ["Y", 2.0]], **t), _vote("B", [["Y", 1.0], ["X", 2.0]], **t)], TAU).decision == "TANYA"


def test_s7_numeric_tau_boundary_inclusive():                           # EDGE-24, EDGE-28
    assert decide([_vote("A", [[10.0]]), _vote("B", [[10.5]])], TAU).decision == "JAWAB"
    assert decide([_vote("A", [[10.0]]), _vote("B", [[10.5001]])], TAU).decision == "TANYA"


def test_s7_different_units_never_equal():                              # EDGE-22
    assert decide([_vote("A", [[5.0]], unit="%"), _vote("B", [[5.0]], unit="orang")], TAU).decision == "TANYA"


def test_s7_checks_all_pairs_not_only_neighbours():                     # EDGE-29
    d = decide([_vote("A", [[0.0]]), _vote("B", [[0.4]]), _vote("C", [[0.8]])], TAU)
    assert d.decision == "TANYA" and len(d.evidence) == 3


def test_s7_tau_null_raises_instead_of_default():                       # EDGE-36
    with pytest.raises(ConfigError):
        setara(_vote("A", [[1.0]]).result, _vote("B", [[1.0]]).result, {"%": None})


def test_s7_execution_error_is_not_empty_or_equal():
    assert decide([_vote("A", [], error="TIMEOUT"), _vote("B", [[1.0]])], TAU).reason_code == "T0"


def test_s7_different_shapes_not_equal():                               # EDGE-33 (PROPOSED K-17)
    assert decide([_vote("A", [[1.0]]), _vote("B", [[1.0], [2.0]])], TAU).decision == "TANYA"


# ---------- Perbaikan katalog/ekstraksi 21 Okt (USULAN K-12/K-18; data SYNTHETIC) ----------
def test_s1_enclitic_nya_only_when_base_is_kamus_token(cat, cfg):
    assert extract("provinsi yang ukuran anya tertinggi", catalog=cat, config=cfg).terms == ["ukuran a"]
    assert extract("ukuran a di betanya", catalog=cat, config=cfg).regions == ["02"]
    assert extract("hanya ukuran a", catalog=cat, config=cfg).terms == ["ukuran a"]       # "hanya" -> "ha" bukan kata kamus
    cfg2 = copy.deepcopy(cfg)
    cfg2["extraction"]["strip_enclitic_nya"] = False
    assert extract("provinsi yang ukuran anya tertinggi", catalog=cat, config=cfg2).terms == []


def test_s1_number_words_set_top_n_and_lebih_is_rank(cat, cfg):
    e = extract("tiga provinsi dengan ukuran a tertinggi", catalog=cat, config=cfg)
    assert (e.operation, e.rank_direction, e.top_n) == ("RANK", "highest", 3)
    e = extract("alfa atau beta, mana yang ukuran a lebih rendah", catalog=cat, config=cfg)
    assert (e.operation, e.rank_direction, e.top_n, e.regions) == ("RANK", "lowest", 1, ["01", "02"])


def test_s1_di_antara_is_not_an_unknown_place(cat, cfg):
    e = extract("di antara alfa dan beta, mana yang ukuran a tertinggi", catalog=cat, config=cfg)
    assert e.unresolved == [] and e.regions == ["01", "02"]


def test_s3_year_only_uses_latest_period_of_that_year_in_intersection(cat, cfg):
    k = resolve(_ext(), catalog=cat)                                   # A_PCT {2025-03, 2025-09}, A_NUM {2025-03}
    out = check_candidates(_ext(period="2025"), k, catalog=cat, config=cfg)
    assert out.period == "2025-03" and out.reason is None              # irisan K, bukan 2025-09 milik A_PCT saja
    e = _ext(terms=["ukuran a persen"], period="2025")
    assert check_candidates(e, resolve(e, catalog=cat), catalog=cat, config=cfg).period == "2025-09"
    out = check_candidates(_ext(period="2026"), k, catalog=cat, config=cfg)
    assert out.reason == "T2" and out.period == "2026"                 # tahun tanpa data: tidak pindah ke tahun lain
    cfg2 = copy.deepcopy(cfg)
    cfg2["decision"]["year_only_period"] = "none"
    assert check_candidates(_ext(period="2025"), k, catalog=cat, config=cfg2).reason == "T2"   # perilaku lama


@pytest.mark.parametrize("cond,ok", [
    ("n.kode_provinsi IN (:wilayah_0, :wilayah_1)", True),
    ("p.kode IN (:wilayah_0, :wilayah_1)", True),
    (":wilayah_0 = n.kode_provinsi AND n.kode_provinsi = :wilayah_1", True),
    ("p.nama IN (:wilayah_0, :wilayah_1)", False),          # teramati 21 Okt: selalu kosong -> T5 palsu bila menang voting
    ("p.nama = :wilayah_0 AND n.kode_provinsi = :wilayah_1", False),
    ("n.kode_provinsi > :wilayah_0 AND n.kode_provinsi < :wilayah_1", False),
])
def test_validator_region_params_only_against_province_code(cond, ok):
    sql = ("SELECT SUM(n.nilai) AS nilai FROM nilai_indikator n JOIN provinsi p ON p.kode = n.kode_provinsi "
           f"WHERE n.kode_indikator = :indikator AND n.periode = :periode AND {cond}")
    assert validate_sql(sql, region_count=2)[0] is ok


def test_s1_negated_and_comparative_poverty_rank_phrases(cat, cfg):
    """21 Okt: "paling tidak miskin" sebelumnya terbaca "paling" = tertinggi (arah terbalik, JAWAB salah)."""
    assert extract("alfa atau beta, mana yang paling tidak miskin", catalog=cat, config=cfg).rank_direction == "lowest"
    assert extract("alfa atau beta, mana yang kurang miskin", catalog=cat, config=cfg).rank_direction == "lowest"
    assert extract("alfa atau beta, mana yang lebih miskin", catalog=cat, config=cfg).rank_direction == "highest"
    assert extract("alfa atau beta, mana yang paling miskin", catalog=cat, config=cfg).rank_direction == "highest"



@pytest.mark.parametrize("shape,tail,ok", [
    (("RANK", "highest", 3), "ORDER BY nilai DESC LIMIT 3", True),
    (("RANK", "highest", 3), "ORDER BY nilai ASC LIMIT 3", False),          # arah terbalik
    (("RANK", "lowest", 1), "ORDER BY nilai ASC LIMIT 2", False),           # top_n salah
    (("RANK", "lowest", 1), "", False),                                     # tanpa ORDER BY
    (("NONE", None, 1), "", True),
    (("NONE", None, 1), "ORDER BY nilai DESC LIMIT 1", False),              # LIMIT memotong wilayah
])
def test_validator_enforces_rank_and_lookup_shape(shape, tail, ok):
    sql = ("SELECT p.nama AS wilayah, n.nilai AS nilai FROM nilai_indikator n JOIN provinsi p ON p.kode = n.kode_provinsi "
           f"WHERE n.kode_indikator = :indikator AND n.periode = :periode {tail}")
    assert validate_sql(sql, shape=shape)[0] is ok


def test_validator_enforces_aggregate_shape():
    base = "FROM nilai_indikator n WHERE n.kode_indikator = :indikator AND n.periode = :periode"
    assert validate_sql(f"SELECT SUM(n.nilai) AS nilai {base}", shape=("SUM", None, 1))[0]
    assert not validate_sql(f"SELECT AVG(n.nilai) AS nilai {base}", shape=("SUM", None, 1))[0]
    assert not validate_sql(f"SELECT SUM(n.nilai) AS nilai {base} LIMIT 1", shape=("SUM", None, 1))[0]
    assert not validate_sql(f"SELECT n.nilai AS nilai {base}", shape=("AVG", None, 1))[0]
