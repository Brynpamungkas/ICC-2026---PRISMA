"""SYNTHETIC checks for evaluation provenance, review and fixed denominators."""
import argparse
import csv
import json

import pytest

from scripts import run_eval


def test_draft_labels_are_rejected_before_loading_answer_sidecar(tmp_path):
    questions = tmp_path / "q.csv"
    questions.write_text("question_id,domain,target_group,source_kind,source_record_id,author,question_text\n"
                         "SYN_Q,kemiskinan,TAK_AMBIGU,tim,SYN,SYN,SYNTHETIC\n")
    labels = tmp_path / "labels.csv"
    from scripts import dataset_tools as dt
    row = {k: "" for k in dt.L_COLS}
    row.update(question_id="SYN_Q", annotator_id="FINAL", question_group="TAK_AMBIGU",
               decision_reference="JAWAB", interpretation_id="I1", indicator_code="SYN_I",
               operation="NONE", reference_sql="SELECT 1", verification_status="DRAFT")
    with labels.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=dt.L_COLS)
        writer.writeheader()
        writer.writerow(row)
    with pytest.raises(SystemExit, match="VERIFIED"):
        run_eval.load_labels(labels, questions)


def test_metrics_keep_manifest_questions_when_records_are_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(run_eval, "load_labels", lambda *a, **kw: {
        q: {"y": "JAWAB", "group": "TAK_AMBIGU", "domain": "kemiskinan", "refs": [], "indicator_codes": []}
        for q in ("SYN_1", "SYN_2")})
    (tmp_path / "manifest.json").write_text(json.dumps({"run_id": "SYN", "split": "dev",
        "conditions": ["K3"], "question_ids": ["SYN_1", "SYN_2"]}))
    (tmp_path / "K3.jsonl").write_text(json.dumps({"question_id": "SYN_1", "decision": "TAHAN",
        "reason_code": "T4", "latency_ms": 1}) + "\n")
    args = argparse.Namespace(run=tmp_path, label_final=tmp_path / "l.csv", pertanyaan=tmp_path / "q.csv")
    assert run_eval.cmd_metrics(args) == 0
    result = json.loads((tmp_path / "metrik_K3.json").read_text())["semua"]
    assert result["Q"] == 2 and result["missing_records"] == ["SYN_2"]


def test_protocol_cannot_claim_one_person_as_two_annotators(tmp_path):
    from scripts.eval_protocol import validate_protocol
    with pytest.raises(SystemExit, match="protokol|penilai"):
        validate_protocol(tmp_path / "missing.json", {"SYN_Q"})


def test_duplicate_records_do_not_silently_replace_each_other():
    from backend.app.eval_metrics import compute
    label = {"SYN": {"y": "JAWAB", "group": "TAK_AMBIGU", "domain": "kemiskinan",
                     "refs": [], "indicator_codes": []}}
    with pytest.raises(ValueError, match="ganda"):
        compute([{"question_id": "SYN", "decision": "JAWAB"},
                 {"question_id": "SYN", "decision": "TAHAN"}], label)
