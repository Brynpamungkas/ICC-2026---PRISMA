"""SYNTHETIC provenance checks; these fixtures are never human research labels."""
import csv
import hashlib
import json

import pytest

from scripts import dataset_tools as dt
from scripts import eval_protocol as ep


def _protocol(tmp_path, monkeypatch, second="SYN_B"):
    monkeypatch.setattr(ep, "ROOT", tmp_path)
    decisions = {"SYN_Q1": "JAWAB", "SYN_Q2": "TANYA"}
    files = {}
    for key, annotator in (("initial_a", "SYN_A"), ("initial_b", second)):
        path = tmp_path / (key + ".csv")
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=dt.L_COLS)
            writer.writeheader()
            for qid, decision in decisions.items():
                row = dict.fromkeys(dt.L_COLS, "")
                row.update(question_id=qid, annotator_id=annotator, decision_reference=decision,
                           reference_sql="SELECT 1", verification_status="VERIFIED")
                writer.writerow(row)
        files[key] = path
    files["agreement_report"] = tmp_path / "agreement.json"
    files["agreement_report"].write_text(json.dumps(dt.cohen_kappa(decisions, decisions)))
    files["reconciliation_log"] = tmp_path / "reconciliation.jsonl"
    files["reconciliation_log"].write_text('{"synthetic": true, "changes": []}\n')
    protocol = {"reviewer": "SYN_REVIEWER", "initial_labels_locked_before_reconciliation": True,
                "llm_draft_opened_after_initial_lock": True}
    protocol.update({key: {"path": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                     for key, p in files.items()})
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    return path


def test_complete_synthetic_protocol_checks_artifacts_and_agreement(tmp_path, monkeypatch):
    result = ep.validate_protocol(_protocol(tmp_path, monkeypatch), {"SYN_Q1", "SYN_Q2"})
    assert result["agreement_N"] == 2 and result["initial_annotators"] == ["SYN_A", "SYN_B"]


def test_same_annotator_is_not_two_independent_humans(tmp_path, monkeypatch):
    with pytest.raises(SystemExit, match="ID yang berbeda"):
        ep.validate_protocol(_protocol(tmp_path, monkeypatch, second="SYN_A"), {"SYN_Q1"})


def test_changed_initial_labels_invalidate_locked_hash(tmp_path, monkeypatch):
    path = _protocol(tmp_path, monkeypatch)
    with (tmp_path / "initial_a.csv").open("a") as stream:
        stream.write("changed\n")
    with pytest.raises(SystemExit, match="hash bukti"):
        ep.validate_protocol(path, {"SYN_Q1"})


def test_llm_exposure_before_lock_is_not_hidden(tmp_path, monkeypatch):
    path = _protocol(tmp_path, monkeypatch)
    protocol = json.loads(path.read_text())
    protocol["llm_draft_opened_after_initial_lock"] = False
    path.write_text(json.dumps(protocol))
    with pytest.raises(SystemExit, match="paparan"):
        ep.validate_protocol(path, {"SYN_Q1"})
