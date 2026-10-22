"""M5@314076f extraction proposals tested on the CPU branch; no model calls."""
import copy
from backend.tests.unit import test_m2_steps as fixtures
from backend.app.steps.s1_extract import extract
from backend.app.steps.s2_resolve import resolve
from backend.app.steps.s3_checks import check_candidates

cat = fixtures.cat
cfg = fixtures.cfg
_ext = fixtures._ext

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


def test_s1_negated_and_comparative_poverty_rank_phrases(cat, cfg):
    """21 Okt: "paling tidak miskin" sebelumnya terbaca "paling" = tertinggi (arah terbalik, JAWAB salah)."""
    assert extract("alfa atau beta, mana yang paling tidak miskin", catalog=cat, config=cfg).rank_direction == "lowest"
    assert extract("alfa atau beta, mana yang kurang miskin", catalog=cat, config=cfg).rank_direction == "lowest"
    assert extract("alfa atau beta, mana yang lebih miskin", catalog=cat, config=cfg).rank_direction == "highest"
    assert extract("alfa atau beta, mana yang paling miskin", catalog=cat, config=cfg).rank_direction == "highest"
