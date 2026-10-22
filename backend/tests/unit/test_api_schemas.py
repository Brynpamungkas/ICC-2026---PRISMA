"""API boundary contracts. All examples are SYNTHETIC."""
import math
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.app.schemas.api import ApiDecision, QuestionResponse, TanyaRequest


def evidence(code="SYN_A", value=1.0):
    return {
        "candidate": {"code": code, "canonical_name": "SYNTHETIC", "unit": "unit contoh"},
        "result": {"candidate_code": code, "columns": ["nilai"], "rows": [[value]],
                   "structure": "NUMBER", "unit": "unit contoh", "error": None},
    }


def test_request_requires_strict_strings_and_uuid4():
    session = str(uuid4())
    assert TanyaRequest(pertanyaan="  contoh  ", id_sesi=session).pertanyaan == "contoh"
    for body in [
        {"pertanyaan": 42, "id_sesi": session},
        {"pertanyaan": " ", "id_sesi": session},
        {"pertanyaan": "q", "id_sesi": "sesi-berbasis-waktu"},
        {"pertanyaan": "q", "id_sesi": session, "sql": "SELECT 1"},
    ]:
        with pytest.raises(ValidationError):
            TanyaRequest.model_validate(body)


@pytest.mark.parametrize("body", [
    {"decision": "JAWAB"},
    {"decision": "JAWAB", "answer": evidence(), "period_used": None},
    {"decision": "TANYA", "evidence": [evidence()], "period_used": "2099-01"},
    {"decision": "TAHAN", "reason_code": None, "suggestion": "contoh"},
    {"decision": "TAHAN", "reason_code": "T1", "suggestion": "contoh", "answer": evidence()},
])
def test_branch_invariants_reject_inconsistent_payloads(body):
    with pytest.raises(ValidationError):
        ApiDecision.model_validate(body)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, "1.234,5"])
def test_numeric_results_reject_nonfinite_or_formatted_values(value):
    with pytest.raises(ValidationError):
        ApiDecision(decision="JAWAB", answer=evidence(value=value), period_used="2099-01")


def test_candidate_result_correspondence_and_row_shape():
    broken = evidence()
    broken["result"]["candidate_code"] = "SYN_OTHER"
    with pytest.raises(ValidationError):
        ApiDecision(decision="JAWAB", answer=broken, period_used="2099-01")
    broken = evidence()
    broken["result"]["rows"] = [[1.0, 2.0]]
    with pytest.raises(ValidationError):
        ApiDecision(decision="JAWAB", answer=broken, period_used="2099-01")


def test_all_candidates_preserved_and_tahan_nulls_explicit():
    body = ApiDecision(decision="TANYA", evidence=[evidence(f"SYN_{i}") for i in range(3)],
                       period_used="2099-01")
    assert len(body.evidence) == 3
    response = QuestionResponse(id_sesi=str(uuid4()), id_log=str(uuid4()),
                                decision=ApiDecision(decision="TAHAN", reason_code="T1", suggestion="contoh"))
    assert response.model_dump()["decision"]["answer"] is None
    assert response.model_dump()["decision"]["period_used"] is None
