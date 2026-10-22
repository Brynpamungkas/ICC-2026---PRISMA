from backend.app.schemas import Decision, ExtractionResult


def test_decision_valid():
    d = Decision(decision="TAHAN", reason_code="T1", suggestion="coba istilah lain")
    assert d.decision == "TAHAN"


def test_decision_invalid_kind():
    import pytest
    with pytest.raises(Exception):
        Decision(decision="MUNGKIN")


def test_extraction_defaults():
    e = ExtractionResult(raw_question="q", terms=["miskin"])
    assert e.operation == "NONE" and e.regions == []
