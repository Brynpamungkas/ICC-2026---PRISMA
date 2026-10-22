"""Prompt acceptance checks, with SYNTHETIC input and examples only."""
import pytest

from backend.app.llm.prompt import build_prompt, extraction_context
from backend.app.schemas import ExtractionResult


def extraction(**updates):
    fields = dict(raw_question="Ukuran contoh", terms=["ukuran contoh"], regions=[],
                  period="2099-01", operation="NONE")
    fields.update(updates)
    return ExtractionResult(**fields)


def test_prompt_explains_binding_to_indicator_code_and_actual_period_column():
    prompt = build_prompt("Ukuran contoh?", "", [])
    assert "kode_indikator = :indikator" in prompt
    assert "periode = :periode" in prompt
    assert "nama_kanonik" in prompt and "bukan" in prompt
    assert "indikator.periode" in prompt


def test_schema_contains_all_four_metadata_tables_without_example_data():
    prompt = build_prompt("Ukuran contoh?", "", [])
    for table in ["provinsi", "indikator", "nilai_indikator", "kamus_istilah"]:
        assert table + "(" in prompt
    assert "definisi_resmi" in prompt and "periode_tersedia" in prompt
    assert "KMS_PERSEN" not in prompt and "KMS_JUMLAH" not in prompt
    assert "Papua Tengah" not in prompt and "Jawa Timur" not in prompt


@pytest.mark.parametrize("direction,order", [("highest", "DESC"), ("lowest", "ASC")])
def test_rank_context_preserves_resolved_operation_period_and_limit(direction, order):
    context = extraction_context(extraction(operation="RANK", rank_direction=direction, top_n=3))
    assert "RANK" in context and order in context and "3" in context
    assert "2099-01" in context and ":periode" in context
    assert "tanpa agregasi" in context


@pytest.mark.parametrize("operation", ["NONE", "SUM", "AVG"])
def test_other_operations_are_preserved_without_guessing(operation):
    assert "operasi=" + operation in extraction_context(extraction(operation=operation))


def test_context_uses_region_bindings_not_invented_region_names():
    context = extraction_context(extraction(regions=["SYN_A", "SYN_B"]))
    assert ":wilayah_0" in context and ":wilayah_1" in context
    assert "SYN_A" not in context and "SYN_B" not in context


def test_dev_examples_are_only_the_explicit_examples_in_their_given_order():
    examples = [{"question": "SYNTHETIC_FIRST", "sql": "SELECT :indikator AS nilai"},
                {"question": "SYNTHETIC_SECOND", "sql": "SELECT :indikator AS nilai"}]
    prompt = build_prompt("SYNTHETIC_QUESTION", "SYNTHETIC_SCHEMA", examples)
    assert prompt.index("SYNTHETIC_FIRST") < prompt.index("SYNTHETIC_SECOND") < prompt.index("SYNTHETIC_QUESTION")
    assert "SYNTHETIC_SCHEMA" in prompt
    assert examples[0]["question"] == "SYNTHETIC_FIRST"
