"""SYNTHETIC checks for adapting the team's system/user prompt to CPU."""
import pytest

from backend.app.llm import prompt as P
from backend.app.schemas import ExtractionResult


def test_system_and_user_remain_separate_without_rewriting_question():
    text = P.build_prompt("Pertanyaan SYNTHETIC?", "", [])
    messages = P.build_messages(text)
    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[0]["content"] == P.SYSTEM_PROMPT
    assert messages[1]["content"] == text
    assert "Do not answer the question or choose an indicator" in messages[0]["content"]


def test_user_sections_follow_d06_with_explicitly_empty_examples():
    text = P.build_prompt("SYNTHETIC?", "", [])
    names = ["SCHEMA_CONTEXT", "RESOLVED_SQL_CONTRACT", "EXTRACTION_CONTEXT", "REVIEWED_DEV_EXAMPLES", "QUESTION"]
    assert [text.index(name + "\n") for name in names] == sorted(text.index(name + "\n") for name in names)
    assert "REVIEWED_DEV_EXAMPLES\n" + P.NO_EXAMPLES in text


@pytest.mark.parametrize("operation", ["SUM", "AVG"])
def test_aggregate_context_has_one_aggregate_value_and_no_grouping(operation):
    ext = ExtractionResult(raw_question="SYNTHETIC", terms=[], regions=["P_SYN"], operation=operation)
    context = P.extraction_context(ext)
    assert f"SELECT {operation}(nilai_indikator.nilai) AS nilai" in context
    assert "tanpa GROUP BY" in context and "tanpa LIMIT" in context


def test_none_operation_does_not_force_text_projection_for_numeric_questions():
    ext = ExtractionResult(raw_question="Berapa nilai ukuran contoh?", terms=[], regions=["P_SYN"], operation="NONE")
    assert "SELECT provinsi.nama AS wilayah" not in P.extraction_context(ext)


@pytest.mark.parametrize("backend", ["vllm", "llama_cpp"])
def test_both_openai_backends_use_the_same_documented_messages(backend, monkeypatch, tmp_path):
    from backend.app.config import load_config
    from backend.app.llm.client import LlmClient

    cfg = load_config()
    cfg["model"]["backend"] = backend
    cfg["transport"]["trace_dir"] = str(tmp_path)
    calls = []

    class Reply:
        status_code = 200
        text = "SYNTHETIC"
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": "SYNTHETIC"}}]}

    def post(url, json, timeout):
        calls.append(json)
        return Reply()

    monkeypatch.setattr("backend.app.llm.client.requests.post", post)
    LlmClient(cfg).generate("SYNTHETIC", 1)
    assert [m["role"] for m in calls[0]["messages"]] == ["system", "user"]


@pytest.mark.parametrize("operation", ["NONE", "RANK", "SUM", "AVG"])
def test_resolved_context_repeats_mandatory_fact_filters_for_every_operation(operation):
    ext = ExtractionResult(raw_question="SYNTHETIC", terms=[], regions=["P_SYN_A", "P_SYN_B"],
                           period="2099-01", operation=operation)
    context = P.extraction_context(ext)
    assert "WHERE nilai_indikator.kode_indikator = :indikator" in context
    assert "AND nilai_indikator.periode = :periode" in context
    assert "AND nilai_indikator.kode_provinsi IN (:wilayah_0, :wilayah_1)" in context
    assert "P_SYN_A" not in context and "P_SYN_B" not in context


def test_final_instruction_repeats_generic_resolved_contract_after_question():
    ext = ExtractionResult(raw_question="Pertanyaan SYNTHETIC?", terms=[], regions=[],
                           period="2099-01", operation="SUM")
    context = P.extraction_context(ext)
    text = P.build_prompt(ext.raw_question, "", [], context)
    suffix = text.split("QUESTION\n" + ext.raw_question, 1)[1]
    assert "WHERE nilai_indikator.kode_indikator = :indikator" in suffix
    assert "SELECT SUM(nilai_indikator.nilai) AS nilai" in suffix
    assert "tanpa GROUP BY" in suffix
    assert ext.raw_question not in suffix


def test_empty_context_does_not_invent_resolved_filters_or_an_operation():
    text = P.build_prompt("SYNTHETIC", "", [], "")
    assert "FINAL_BINDING_CHECK" not in text
