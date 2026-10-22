"""Run the three paper A-4 cases against the configured real model and database.

Each run is retained, including failures. This is a local integration check, not
evaluation of 180 questions or automatic acceptance of G2/G3/G4. Run in a normal
terminal while the configured model service is running:
PRISMA_CONFIG=config/local.cpu.yaml .venv/bin/python -m scripts.smoke_pipeline
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import time
from uuid import uuid4

from backend.app.catalog import get_catalog
from backend.app.config import ROOT, load_config
from backend.app.llm.client import LlmClient
from backend.app.orchestrator import clarify, run_question_with_log
from backend.app.sqlguard.executor import run_query
from backend.app.sqlguard.validator import validate_sql


def check_case(decision: dict, expected_decision: str, references: dict,
               expected_reason: str | None = None) -> list[str]:
    errors = []
    if decision["decision"] != expected_decision:
        return [f"expected {expected_decision}, received {decision['decision']}"]
    if expected_decision == "TAHAN":
        return [] if decision.get("reason_code") == expected_reason else ["unexpected hold reason"]
    items = [decision["answer"]] if expected_decision == "JAWAB" else decision["evidence"]
    codes = [item["candidate"]["code"] for item in items]
    if len(codes) != len(set(codes)) or set(codes) != set(references):
        errors.append("candidate set differs from reference")
    for item in items:
        result = item["result"]
        if result.get("error") is not None or result["rows"] != references.get(item["candidate"]["code"]):
            errors.append("execution status or original rows differ from reference")
    return errors


def _reference(sql: str, params: dict, config: dict) -> list[list]:
    """Reviewed A-4 reference queries only; never supply model completions."""
    valid, reason = validate_sql(sql)
    if not valid:
        raise ValueError("Reference SQL failed validation: " + str(reason))
    result = run_query(sql, params, db_path=config["execution"]["db_path"])
    if result.error or not result.rows or any(value is None for row in result.rows for value in row):
        raise ValueError("Reference snapshot is unavailable or incomplete")
    return result.rows


def run(config: dict, output: Path) -> bool:
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    cfg = deepcopy(config)
    cfg["transport"]["trace_dir"] = str(output.resolve() / "transport")
    cfg["logging"]["trace_dir"] = str(output.resolve() / "pipeline")
    catalog = get_catalog()
    period = "2025-09"  # Paper A-4 snapshot; do not substitute a different snapshot silently.
    rank_sql = ("SELECT p.nama AS wilayah,n.nilai AS nilai FROM nilai_indikator n "
                "JOIN provinsi p ON p.kode=n.kode_provinsi WHERE n.kode_indikator=:indikator "
                "AND n.periode=:periode ORDER BY n.nilai DESC LIMIT 1")
    session = str(uuid4())
    report = {
        "run_id": output.name, "purpose": "PAPER_A4_LOCAL_INTEGRATION_NOT_FINAL_EVALUATION",
        "recorded_at": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
        "platform": platform.platform(), "backend": cfg["model"]["backend"],
        "model": cfg["model"]["name"], "model_sha256": cfg["model"].get("digest"),
        "sampling": cfg["sampling"], "prompt_version": cfg["prompt"]["version"],
        "catalog_hash": catalog.version, "baseline_gate_passed": False, "results": [],
        "limitations": ["CPU fallback is separate from vLLM/AWQ/N64", "Not an API/UI test",
                        "API/UI projection of the diagnostic sidecar is not tested here",
                        "Not p50/p95 or research accuracy", "No final gate is accepted automatically"],
    }
    report["code_commit"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
        capture_output=True, text=True, check=True).stdout.strip()
    report["code_dirty"] = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        capture_output=True, text=True, check=True).stdout)
    names = sorted({str(path.relative_to(ROOT)) for folder in [ROOT / "backend/app", ROOT / "scripts"]
                    for path in folder.rglob("*.py")})
    report["source_sha256"] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}
    report["resolved_config_sha256"] = hashlib.sha256(
        json.dumps(cfg, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    report["software_versions"] = {name: importlib.metadata.version(name)
                                   for name in ["pydantic", "sqlglot", "pandas", "requests", "pyyaml"]}
    database = ROOT / cfg["execution"]["db_path"]
    with database.open("rb") as stream:
        report["database_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    (output / "resolved_config.json").write_text(json.dumps(cfg, indent=2) + "\n")

    def save():
        (output / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    save()
    cases = [("GOLD-01", "Provinsi mana yang paling miskin?", "TANYA"),
             ("GOLD-02", "Berapa total penduduk miskin di Pulau Jawa?", "JAWAB"),
             ("GOLD-03", "Berapa IPM Jawa Barat?", "TAHAN")]
    for identifier, question, expected in cases:
        row = {"case_id": identifier, "question": question, "expected": expected,
               "passed": False, "references": {}, "transport_trace": None}
        report["results"].append(row)
        client = LlmClient(cfg)
        started = time.monotonic()
        try:
            references = {}
            if identifier == "GOLD-01":
                references = {code: _reference(rank_sql, {"indikator": code, "periode": period}, cfg)
                              for code in ["KMS_PERSEN", "KMS_JUMLAH"]}
            elif identifier == "GOLD-02":
                regions = sorted(catalog.kamus[("pulau", "jawa")]["wilayah"])
                bindings = {f"wilayah_{i}": code for i, code in enumerate(regions)}
                params = {"indikator": "KMS_JUMLAH", "periode": period, **bindings}
                sql = ("SELECT SUM(n.nilai) AS nilai FROM nilai_indikator n "
                       "WHERE n.kode_indikator=:indikator AND n.periode=:periode AND n.kode_provinsi IN ("
                       + ",".join(":" + key for key in bindings) + ")")
                references = {"KMS_JUMLAH": _reference(sql, params, cfg)}
            row["references"] = references
            decision, record = run_question_with_log(question, llm=client, config=cfg, catalog=catalog,
                session_id=session, log_path=str(output / (identifier + ".jsonl")))
            payload = decision.model_dump()
            row["decision"] = payload
            row["pipeline_trace"] = str(Path(cfg["logging"]["trace_dir"]) / (record.run_id + ".trace.jsonl"))
            row["errors"] = check_case(payload, expected, references, "T1" if expected == "TAHAN" else None)
            if expected != "TAHAN" and decision.period_used != period:
                row["errors"].append("resolved period differs from paper snapshot")
            row["received_skeletons"] = len(record.skeletons)
            row["valid_skeletons"] = sum(item.valid for item in record.skeletons)
            if expected != "TAHAN" and len(record.skeletons) != cfg["sampling"]["n_samples"]:
                row["errors"].append("received sample count differs from requested N")
            if decision.decision == "TANYA":
                # Exercise every evidence choice independently in the pure clarifier.
                # HTTP persistence/idempotency is tested separately, not claimed here.
                choices = [clarify(decision, item.candidate.code).model_dump() for item in decision.evidence]
                row["clarifications"] = choices
                for answer in choices:
                    code = answer["answer"]["candidate"]["code"]
                    row["errors"].extend(check_case(answer, "JAWAB", {code: references.get(code)}))
            row["passed"] = not row["errors"]
        except Exception as exc:
            row["failure"] = {"category": type(exc).__name__, "message": str(exc)}
        finally:
            row["duration_s"] = time.monotonic() - started
            row["transport_trace"] = str(client.last_trace_path) if client.last_trace_path else None
            save()
        print(f"{identifier}: {'PASS' if row['passed'] else 'FAIL'}", flush=True)
    return all(row["passed"] for row in report["results"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    name = "pipeline-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex
    output = args.out or ROOT / "eval/runs" / name
    passed = run(load_config(), output)
    print(f"Bukti: {output}. Tidak meluluskan G2/G3/G4 otomatis.")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
