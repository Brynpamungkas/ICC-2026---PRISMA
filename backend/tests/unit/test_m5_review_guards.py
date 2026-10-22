"""SYNTHETIC safeguards for the agreed human annotation workflow."""
import json

import pytest

from backend.app.config import ConfigError


def test_unreviewed_examples_cannot_be_loaded(tmp_path):
    from backend.app.llm.examples import load_examples
    p = tmp_path / "examples.json"
    p.write_text(json.dumps({"ditinjau_oleh": "", "contoh": []}))
    with pytest.raises(ConfigError, match="ditinjau"):
        load_examples({"prompt": {"examples_file": str(p), "few_shot_k": 4}})


def test_no_examples_profile_is_explicitly_empty():
    from backend.app.llm.examples import load_examples
    assert load_examples({"prompt": {"examples_file": None, "few_shot_k": 4}}) == []


def test_answer_tolerance_is_applied_without_rounding():
    from backend.app.eval_metrics import answer_matches
    assert not answer_matches([[1.00000001]], "2099-01", {
        "rows": [[1.00000149]], "period": "2099-01", "operation": "NONE"})


def test_number_evidence_allows_row_labels_but_keeps_numbers_strict():
    from backend.app.schemas.api import ApiDecision
    from backend.tests.unit.test_api_schemas import evidence
    ev = evidence()
    ev["result"].update(columns=["wilayah", "nilai"], rows=[["SYNTHETIC", 1.0]])
    assert ApiDecision.model_validate({"decision": "JAWAB", "answer": ev, "period_used": "2099-01"})
    ev["result"]["rows"] = [["SYNTHETIC", "1,0"]]
    with pytest.raises(ValueError):
        ApiDecision.model_validate({"decision": "JAWAB", "answer": ev, "period_used": "2099-01"})
