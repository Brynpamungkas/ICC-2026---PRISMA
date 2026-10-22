"""SYNTHETIC checks of the smoke harness, not model/evaluation results."""
from scripts.smoke_pipeline import check_case


def item(code, rows, *, error=None):
    return {"candidate": {"code": code}, "result": {"rows": rows, "error": error}}


def test_clarification_requires_all_reference_candidates_and_original_results():
    expected = {"A_SYN": [["Alfa", 1]], "B_SYN": [["Beta", 2]]}
    decision = {"decision": "TANYA", "evidence": [item(code, rows) for code, rows in expected.items()]}
    assert check_case(decision, "TANYA", expected) == []
    decision["evidence"].pop()
    assert check_case(decision, "TANYA", expected)


def test_answer_checks_values_not_just_the_decision():
    decision = {"decision": "JAWAB", "answer": item("A_SYN", [[123]])}
    assert check_case(decision, "JAWAB", {"A_SYN": [[456]]})


def test_hold_requires_the_expected_reason():
    assert check_case({"decision": "TAHAN", "reason_code": "T1"}, "TAHAN", {}, "T1") == []
    assert check_case({"decision": "TAHAN", "reason_code": "T0"}, "TAHAN", {}, "T1")


def test_execution_error_cannot_pass_as_an_answer():
    decision = {"decision": "JAWAB", "answer": item("A_SYN", [[123]], error="SQL_ERROR")}
    assert check_case(decision, "JAWAB", {"A_SYN": [[123]]})
