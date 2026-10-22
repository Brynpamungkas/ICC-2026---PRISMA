"""M3 prompt v0.2.0: SYS-SQL-A system message + USR-SQL-A user sections (D06 PRM-05). SYNTHETIC inputs only."""
from backend.app.config import load_config
from backend.app.llm import prompt as P
from backend.app.llm.client import LlmClient
from backend.app.schemas import ExtractionResult


def test_user_prompt_sections_in_d06_order_and_examples_explicitly_empty():
    text = P.build_prompt("Pertanyaan SYNTHETIC?", "", [], "Hasil ekstraksi: operasi=NONE")
    names = ["SCHEMA_CONTEXT", "RESOLVED_SQL_CONTRACT", "EXTRACTION_CONTEXT", "REVIEWED_DEV_EXAMPLES", "QUESTION"]
    pos = [text.index(n + "\n") for n in names]
    assert pos == sorted(pos)
    assert "REVIEWED_DEV_EXAMPLES\n" + P.NO_EXAMPLES in text
    assert text.rstrip().endswith("Generate the SQL skeleton.")


def test_user_prompt_has_no_indicator_codes():
    text = P.build_prompt("Pertanyaan SYNTHETIC?", "", [], "")
    for code in ("KMS_PERSEN", "KMS_JUMLAH", "TPT_PERSEN", "APM_SMA"):
        assert code not in text
    assert ":indikator" in text


def test_examples_rendered_only_when_given():
    text = P.build_prompt("q", "", [{"question": "contoh SYNTHETIC", "sql": "SELECT 1"}], "")
    section = text.split("REVIEWED_DEV_EXAMPLES\n")[1].split("\n\nQUESTION\n")[0]
    assert section == "Pertanyaan: contoh SYNTHETIC\nSQL: SELECT 1"


def test_extraction_context_mentions_period_param_and_regions():
    ext = ExtractionResult(raw_question="q", terms=["t"], regions=["31", "32"], period="2099-01",
                           rank_direction="highest", top_n=3)
    ctx = P.extraction_context(ext)
    assert "periode=:periode" in ctx and "nilai_indikator.kode_provinsi IN (:wilayah_0, :wilayah_1)" in ctx and "ORDER BY nilai DESC LIMIT 3" in ctx
    assert "2099-01" not in ctx                     # period goes in as a bind parameter, not a literal


def test_vllm_payload_sends_system_then_user(monkeypatch):
    seen = {}

    class R:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": "SELECT 1"}}]}

    def fake_post(url, json=None, timeout=None):
        seen["payload"] = json
        return R()

    import backend.app.llm.client as mod
    monkeypatch.setattr(mod.requests, "post", fake_post)
    LlmClient().generate("USER", 2)
    msgs = seen["payload"]["messages"]
    assert [m["role"] for m in msgs] == ["system", "user"]
    assert msgs[0]["content"] == P.SYSTEM_PROMPT and msgs[1]["content"] == "USER"


def test_prompt_version_bumped_with_change():
    assert str(load_config()["prompt"]["version"]) not in {"0.1.0", "0.2.0", "0.2.1", "0.2.2"}      # contract text changed in 0.2.3


def test_contract_names_only_validator_parameters():
    import re
    params = set(re.findall(r":([a-z_]+)", P.RULES))
    assert params <= {"indikator", "periode", "wilayah_"}                          # no stray :k (seen in probe v0.2.0)


def test_aggregate_shape_has_no_group_by_and_no_stray_params():
    import re
    ext = ExtractionResult(raw_question="q", terms=["t"], regions=["31", "32"], operation="AVG")
    ctx = P.extraction_context(ext)
    assert "SELECT AVG(nilai_indikator.nilai) AS nilai" in ctx and "tanpa GROUP BY" in ctx
    for e in (ext, ExtractionResult(raw_question="q", terms=["t"], rank_direction="lowest", top_n=2)):
        params = set(re.findall(r":([a-z_]+)", P.extraction_context(e)))
        assert params <= {"periode", "wilayah_"}


def test_dev_examples_v030_are_dev_only_valid_and_rendered_for_k1_and_k3():
    """v0.3.0 (21 Okt): contoh hanya dari DEV, lolos validator dengan bentuk S1-nya sendiri, dan tampil di K1 & K3."""
    import json

    from backend.app.config import ROOT
    from backend.app.llm.examples import load_examples
    from backend.app.sqlguard.validator import validate_sql
    from backend.app.steps.s1_extract import extract
    cfg = load_config()
    ex = load_examples(cfg)
    split = json.loads((ROOT / "eval/testset/split_seed-prisma-21okt.json").read_text(encoding="utf-8"))
    assert 0 < len(ex) <= cfg["prompt"]["few_shot_k"] and all(e["id"] in split["dev"] for e in ex)
    for e in ex:
        x = extract(e["question"], config=cfg)
        assert validate_sql(e["sql"], region_count=len(x.regions), shape=(x.operation, x.rank_direction, x.top_n)) == (True, None)
        assert e["context"].startswith("Hasil ekstraksi:")
    k3 = P.build_prompt("q", "", ex, "")
    k1 = P.build_k1_prompt("q", [("A", "a", "%")], "", ex)
    assert ex[0]["sql"] in k3 and "INDIKATOR: " + ex[0]["indicator"] in k1 and "INDIKATOR:" not in k3
