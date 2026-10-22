"""SYNTHETIC HTTP fixtures, not evidence of model quality or G-ENV."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
import requests

from backend.app.config import ConfigError, load_config
from backend.app.llm.client import LlmClient, LlmUnavailable


@pytest.fixture
def config(tmp_path):
    cfg = deepcopy(load_config())
    cfg["transport"] = {"timeout_s": 17, "trace_dir": str(tmp_path / "transport")}
    return cfg


class Reply:
    status_code = 200

    def __init__(self, body):
        self.body = body
        self.text = json.dumps(body)

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


def read_trace(config):
    files = list(Path(config["transport"]["trace_dir"]).glob("*.json"))
    assert len(files) == 1
    return json.loads(files[0].read_text())


def test_one_request_preserves_frequency_order_and_metadata(config, monkeypatch):
    body = {"id": "SYNTHETIC", "choices": [
        {"index": 2, "message": {"content": "SELECT a"}, "finish_reason": "stop"},
        {"index": 0, "message": {"content": "SELECT a"}, "finish_reason": "length"},
        {"index": 1, "message": {"content": "SELECT b"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7}}
    calls = []

    def post(url, json, timeout):
        calls.append((url, json, timeout))
        return Reply(body)

    monkeypatch.setattr(requests, "post", post)
    assert LlmClient(config).generate("SYNTHETIC", 3) == ["SELECT a", "SELECT a", "SELECT b"]
    assert len(calls) == 1 and calls[0][2] == 17
    assert calls[0][1]["n"] == 3
    assert calls[0][1]["seed"] == config["sampling"]["seed"]
    trace = read_trace(config)
    assert trace["response"] == body
    assert trace["requested_n"] == trace["received_n"] == 3
    assert trace["status"] == "COMPLETE" and trace["duration_s"] >= 0


def test_partial_samples_are_not_retried_padded_or_dropped(config, monkeypatch):
    calls = []

    def post(*args, **kwargs):
        calls.append(1)
        return Reply({"choices": [{"message": {"content": "one"}}]})

    monkeypatch.setattr(requests, "post", post)
    assert LlmClient(config).generate("SYNTHETIC", 64) == ["one"]
    assert calls == [1]
    trace = read_trace(config)
    assert trace["status"] == "PARTIAL" and trace["received_n"] == 1
    assert trace["requested_n"] == 64


@pytest.mark.parametrize("body", [None, [], {}, {"choices": None}, {"choices": []},
    {"choices": [None]}, {"choices": [{}]}, {"choices": [{"message": None}]},
    {"choices": [{"message": {"content": None}}]},
    {"choices": [{"message": {"content": 5}}]}])
def test_malformed_response_is_a_service_failure(config, monkeypatch, body):
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: Reply(body))
    with pytest.raises(LlmUnavailable):
        LlmClient(config).generate("SYNTHETIC", 1)
    assert read_trace(config)["status"] == "FAILED"


@pytest.mark.parametrize("failure", [requests.Timeout, requests.ConnectionError, requests.HTTPError])
def test_failures_are_archived_without_retry(config, monkeypatch, failure):
    calls = []

    def post(*args, **kwargs):
        calls.append(1)
        raise failure("SYNTHETIC")

    monkeypatch.setattr(requests, "post", post)
    with pytest.raises(LlmUnavailable):
        LlmClient(config).generate("SYNTHETIC", 2)
    trace = read_trace(config)
    assert calls == [1] and trace["received_n"] == 0
    assert trace["error_category"] == failure.__name__


def test_llama_cpp_uses_explicit_openai_profile(config, monkeypatch):
    config["model"].update(backend="llama_cpp", name="SYNTHETIC-GGUF")
    calls = []

    def post(url, json, timeout):
        calls.append((url, json))
        return Reply({"choices": [{"message": {"content": "SQL"}}]})

    monkeypatch.setattr(requests, "post", post)
    assert LlmClient(config).generate("SYNTHETIC", 1) == ["SQL"]
    assert calls[0][1]["model"] == "SYNTHETIC-GGUF"


def test_unknown_backend_never_switches_automatically(config):
    config["model"]["backend"] = "unknown"
    with pytest.raises(ConfigError):
        LlmClient(config)


@pytest.mark.parametrize("n", [0, -1, True, 1.5])
def test_invalid_count_is_rejected(config, n):
    with pytest.raises(ValueError):
        LlmClient(config).generate("SYNTHETIC", n)


def test_readiness_checks_identity_without_sampling(config, monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return Reply({"data": [{"id": config["model"]["name"]}]})

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(requests, "post", lambda *a, **kw: pytest.fail("readiness must not sample"))
    assert LlmClient(config).is_ready() is True
    assert calls == [config["api"]["model_health_url"], config["api"]["model_list_url"]]


def test_readiness_rejects_other_model(config, monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **kw: Reply({"data": [{"id": "OTHER"}]}))
    assert LlmClient(config).is_ready() is False


def test_explicit_config_wins_over_local_environment(tmp_path, monkeypatch):
    path = tmp_path / "trial.yaml"
    path.write_text("purpose: SYNTHETIC\n")
    monkeypatch.setenv("PRISMA_CONFIG", str(path))
    assert load_config() == {"purpose": "SYNTHETIC"}
    assert load_config("config/config.yaml")["sampling"]["n_samples"] == 64
