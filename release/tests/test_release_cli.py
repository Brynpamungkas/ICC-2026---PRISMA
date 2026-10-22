"""Release boundary tests: source tampering, absent model and metadata provenance."""

import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location(
    "release_cli", Path(__file__).resolve().parents[2] / "tools/release_cli.py"
)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def test_exported_source_and_evidence_are_intact():
    core, evidence = cli.verify_sources()
    assert core > 0 and evidence > 0


def test_modified_source_is_rejected_without_rewriting_it(tmp_path):
    (tmp_path / "release").mkdir()
    p = tmp_path / "core.py"
    p.write_text("original")
    manifest = {
        "files": [
            {"path": "core.py", "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        ],
        "evidence_files": [],
    }
    (tmp_path / "release/source_manifest.json").write_text(json.dumps(manifest))
    p.write_text("modified")
    with pytest.raises(RuntimeError, match="core.py"):
        cli.verify_sources(tmp_path)
    assert p.read_text() == "modified"


def test_missing_evidence_is_rejected(tmp_path):
    (tmp_path / "release").mkdir()
    (tmp_path / "release/source_manifest.json").write_text(
        json.dumps(
            {
                "files": [],
                "evidence_files": [{"path": "missing.json", "sha256": "0" * 64}],
            }
        )
    )
    with pytest.raises(RuntimeError, match="missing.json"):
        cli.verify_sources(tmp_path)


def test_profile_matches_export_source_and_real_runtime():
    prof = cli.profile()
    manifest = json.loads((cli.ROOT / "release/source_manifest.json").read_text())
    assert prof["source_commit"] == manifest["source_commit"]
    assert prof["model"]["backend"] in {"llama_cpp", "vllm"}
    assert len(prof["model"]["sha256"]) == 64
