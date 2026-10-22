"""SYNTHETIC responses: these are not real model measurements."""
import json
from pathlib import Path

import pytest

from backend.app.config import load_config
from backend.app.llm.client import LlmUnavailable
from scripts.smoke_vllm import run_smoke


@pytest.mark.parametrize("count,finish,expected", [(2, "stop", True), (1, "stop", False),
                                                 (2, "length", False), (3, "stop", False)])
def test_smoke_requires_exact_count_and_complete_outputs(tmp_path, count, finish, expected):
    class Client:
        def __init__(self, config):
            self.directory = Path(config["transport"]["trace_dir"])

        def generate(self, prompt, n):
            self.directory.mkdir(parents=True)
            self.last_trace_path = self.directory / "synthetic.json"
            self.last_trace_path.write_text(json.dumps({"response": {"choices": [
                {"index": i, "message": {"content": "SYNTHETIC"}, "finish_reason": finish}
                for i in range(count)]}}))
            return ["SYNTHETIC"] * count

    directory = tmp_path / "run"
    assert run_smoke(load_config(), [2], directory, client_factory=Client) is expected
    summary = json.loads((directory / "summary.json").read_text())
    assert summary["results"][0]["passed_transport"] is expected
    assert summary["synthetic_prompt"] is True
    assert summary["baseline_gate_passed"] is False


def test_failed_run_is_retained_and_cannot_be_overwritten(tmp_path):
    class Client:
        last_trace_path = None

        def __init__(self, config):
            pass

        def generate(self, prompt, n):
            raise LlmUnavailable("SYNTHETIC")

    directory = tmp_path / "run"
    assert run_smoke(load_config(), [1], directory, client_factory=Client) is False
    summary = json.loads((directory / "summary.json").read_text())
    assert summary["results"][0]["error_category"] == "LlmUnavailable"
    with pytest.raises(FileExistsError):
        run_smoke(load_config(), [1], directory, client_factory=Client)
