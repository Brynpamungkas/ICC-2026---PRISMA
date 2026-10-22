"""SYNTHETIC diagnostics checks. Trace data must not change pipeline decisions."""
import json
import hashlib
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from backend.app.config import load_config
from backend.app.schemas import Candidate, ExtractionResult, SqlSkeleton
from backend.app.sqlguard.executor import RawResult


def test_trace_does_not_overwrite_another_run(tmp_path):
    from backend.app.logging.trace import PipelineTrace

    trace = PipelineTrace(tmp_path, "a" * 32)
    trace.emit("start", {"fixture": "SYNTHETIC"})
    trace.emit("complete", {"value": None})
    rows = [json.loads(line) for line in trace.path.read_text().splitlines()]
    assert [row["sequence"] for row in rows] == [0, 1]
    assert [row["event"] for row in rows] == ["start", "complete"]
    assert rows[-1]["data"]["value"] is None
    assert trace.path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        PipelineTrace(tmp_path, "a" * 32)


def test_disabled_trace_does_not_create_files(tmp_path):
    from backend.app.logging.trace import PipelineTrace

    trace = PipelineTrace(None, "a" * 32)
    trace.emit("unused", {"not_serializable": object()})
    assert trace.path is None
    assert list(tmp_path.iterdir()) == []


def test_reason_sets_are_serializable_without_sorting_result_rows(tmp_path):
    from backend.app.logging.trace import PipelineTrace

    failures = {"omega", "sigma"}
    rows = [["Beta", 2], ["Alfa", 1]]
    trace = PipelineTrace(tmp_path, "b" * 32)
    trace.emit("SYNTHETIC", {"failures": failures, "rows": rows})
    data = json.loads(trace.path.read_text())["data"]
    assert data["failures"] == ["omega", "sigma"]
    assert data["rows"] == rows and failures == {"omega", "sigma"}


def test_execution_trace_preserves_positions_parameters_errors_and_duplicate_frequency(monkeypatch):
    from backend.app.steps.s5_execute import execute_all

    calls, events = [], []

    def query(sql, params, **kwargs):
        calls.append((sql, params.copy()))
        return RawResult(["nilai"], [[None]]) if params["indikator"] == "A_SYN" else RawResult([], [], "TIMEOUT")

    monkeypatch.setattr("backend.app.steps.s5_execute.run_query", query)
    sql = "SELECT nilai FROM nilai_indikator WHERE kode_indikator=:indikator"
    skeletons = [SqlSkeleton(sql=sql, valid=True), SqlSkeleton(sql="invalid", valid=False),
                 SqlSkeleton(sql=sql, valid=True)]
    candidates = [Candidate(code=code, canonical_name=code, unit="unit contoh") for code in ["A_SYN", "B_SYN"]]
    catalog = SimpleNamespace(indicators={code: SimpleNamespace(unit="unit contoh") for code in ["A_SYN", "B_SYN"]})
    extraction = ExtractionResult(raw_question="SYNTHETIC", terms=[], regions=["P_SYN"], period="2099-01", operation="NONE")
    vectors = execute_all(skeletons, candidates, extraction, catalog=catalog, observer=events.append)
    assert len(vectors) == 2 and len(calls) == 4
    assert [e["sample_position"] for e in events] == [0, 0, 2, 2]
    assert [e["candidate_position"] for e in events] == [0, 1, 0, 1]
    assert all(e["duration_ms"] >= 0 for e in events)
    assert all(e["parameters"]["periode"] == "2099-01" and e["parameters"]["wilayah_0"] == "P_SYN" for e in events)
    assert [e["result"]["error"] for e in events] == [None, "TIMEOUT", None, "TIMEOUT"]
    assert vectors[0][0].rows == [[None]] and events[0]["result"]["rows"] == [[None]]


def test_early_hold_trace_has_only_executed_steps_and_original_decision(tmp_path):
    from backend.app.orchestrator import run_question_with_log

    cfg = load_config()
    cfg["logging"]["trace_dir"] = str(tmp_path)
    decision, record = run_question_with_log("SYNTHETIC istilah tidak dikenal", config=cfg)
    assert decision.reason_code == "T1"
    path = tmp_path / (record.run_id + ".trace.jsonl")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows[0]["event"] == "start" and rows[-1]["event"] == "complete"
    assert rows[-1]["data"]["record"]["decision"] == decision.model_dump()
    assert {r["data"]["stage"] for r in rows if r["event"] == "stage"} == {"s1", "s2"}
    assert "s4" not in record.latency_ms


def test_invalid_run_identifier_cannot_escape_trace_directory(tmp_path):
    from backend.app.logging.trace import PipelineTrace

    with pytest.raises(ValueError):
        PipelineTrace(tmp_path, "../outside")
    assert not (Path(tmp_path).parent / "outside.trace.jsonl").exists()


@pytest.mark.parametrize("operation", ["RANK", "SUM"])
def test_full_trace_preserves_pipeline_output_and_every_valid_sample(tmp_path, operation):
    from backend.app.catalog import Catalog, IndicatorMeta
    from backend.app.llm.mock import MockLlmClient
    from backend.app.orchestrator import run_question_with_log
    from scripts.catalog_lib import create_schema

    database = tmp_path / "SYNTHETIC.sqlite"
    connection = sqlite3.connect(database)
    create_schema(connection)
    connection.executemany("INSERT INTO provinsi VALUES (?,?)", [("P_A", "Alfa"), ("P_B", "Beta")])
    codes = ["A_SYN", "B_SYN"]
    units = {"A_SYN": "%", "B_SYN": "orang"}
    for code in codes:
        connection.execute("INSERT INTO indikator VALUES (?,?,?,?,?,?,?)",
                           (code, code, "SYNTHETIC", units[code], "SYNTHETIC", "P_A|P_B", "2099-01"))
    connection.executemany("INSERT INTO nilai_indikator VALUES (?,?,?,?)",
                           [("P_A", "A_SYN", "2099-01", 10), ("P_B", "A_SYN", "2099-01", 1),
                            ("P_A", "B_SYN", "2099-01", 1), ("P_B", "B_SYN", "2099-01", 20)])
    connection.commit()
    connection.close()
    catalog = Catalog(indicators={code: IndicatorMeta(code, code, "SYNTHETIC", units[code], "SYNTHETIC",
                      frozenset({"P_A", "P_B"}), frozenset({"2099-01"})) for code in codes},
                      provinces={"P_A": "Alfa", "P_B": "Beta"})
    catalog.kamus = {("ukuran", "contoh"): {"indikator": set(codes)}}
    catalog.operations = {("total",): "SUM"}
    sql = ("SELECT p.nama AS wilayah,n.nilai AS nilai FROM nilai_indikator n JOIN provinsi p "
           "ON p.kode=n.kode_provinsi WHERE n.kode_indikator=:indikator AND n.periode=:periode ORDER BY n.nilai DESC LIMIT 1")
    if operation == "SUM":
        sql = "SELECT SUM(n.nilai) AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:indikator AND n.periode=:periode"
    cfg = load_config()
    cfg["sampling"]["n_samples"] = 3  # SYNTHETIC batch; not a changed runtime N.
    cfg["logging"]["trace_dir"] = None
    question = "Provinsi dengan ukuran contoh tertinggi" if operation == "RANK" else "Berapa total ukuran contoh?"
    def ask():
        client = MockLlmClient([sql, "DROP TABLE provinsi", sql])
        transport = tmp_path / "SYNTHETIC-transport.json"
        transport.write_text('{"purpose":"SYNTHETIC_TEST_ONLY"}')
        client.last_trace_path = transport
        return run_question_with_log(question, config=cfg, catalog=catalog, db_path=database,
                                     llm=client)
    original, _ = ask()
    cfg["logging"]["trace_dir"] = str(tmp_path / "trace")
    observed, record = ask()
    assert original.model_dump() == observed.model_dump()
    assert observed.decision == ("TANYA" if operation == "RANK" else "JAWAB")
    rows = [json.loads(line) for line in (tmp_path / "trace" / (record.run_id + ".trace.jsonl")).read_text().splitlines()]
    assert rows[0]["data"]["execution"]["db_path"] == str(database)
    executions = [row["data"] for row in rows if row["event"] == "execution"]
    assert len(executions) == (4 if operation == "RANK" else 2)
    assert [v.votes for v in record.votes] == ([2, 2] if operation == "RANK" else [2])
    assert [e["sample_position"] for e in executions] == ([0, 0, 2, 2] if operation == "RANK" else [0, 2])
    vector_stage = next(row for row in rows if row["event"] == "stage" and row["data"]["stage"] == "s5")
    assert len(vector_stage["data"]["value"]) == 2
    transport = next(row["data"] for row in rows if row["event"] == "model_transport")
    assert transport["sha256"] == hashlib.sha256(Path(transport["path"]).read_bytes()).hexdigest()
    assert rows[-1]["event"] == "complete"
