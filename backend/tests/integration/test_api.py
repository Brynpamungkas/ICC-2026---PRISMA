"""Offline API contracts; SYNTHETIC fixtures, no real model calls."""
import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.api.routes import ApiServices, LogStore, get_services
from backend.app.catalog import Catalog, IndicatorMeta
from backend.app.config import load_config
from backend.app.llm.mock import MockLlmClient
from backend.app.main import create_app
from backend.app.schemas import Candidate, Decision, Evidence, ExecResult, LogRecord
from backend.app.schemas.api import ServiceHealth


def ev(code):
    return Evidence(candidate=Candidate(code=code, canonical_name="SYNTHETIC", unit="unit contoh"),
                    result=ExecResult(candidate_code=code, columns=["wilayah", "nilai"],
                                      rows=[[code, 1.0]], structure="TEXT", unit="unit contoh"))


@pytest.fixture
def env(tmp_path):
    cfg = copy.deepcopy(load_config())
    cfg["api"]["log_dir"] = str(tmp_path / "logs")
    cat = Catalog(
        indicators={"SYN_A": IndicatorMeta("SYN_A", "SYNTHETIC", "SYNTHETIC", "unit contoh",
                                          "SYNTHETIC", frozenset({"01"}), frozenset({"2099-01"}))},
        provinces={"01": "SYNTHETIC"},
    )
    calls = []

    def runner(question, **kwargs):
        calls.append((question, kwargs))
        if question == "ambigu":
            d = Decision(decision="TANYA", evidence=[ev("SYN_A"), ev("SYN_B"), ev("SYN_C")],
                         period_used="2099-01")
        elif question.startswith("T"):
            d = Decision(decision="TAHAN", reason_code=question, suggestion="SYNTHETIC")
        else:
            d = Decision(decision="JAWAB", answer=ev("SYN_A"), period_used="2099-01")
        rec = LogRecord(run_id=uuid4().hex, session_id=kwargs["session_id"], question=question,
                        decision=d, latency_ms={"s1": 1.0})
        return d, rec

    def ready():
        return ServiceHealth(status="AVAILABLE", checked_at="2099-01-01T00:00:00Z")

    services = ApiServices(config=cfg, store=LogStore(Path(cfg["api"]["log_dir"])),
                           catalog_loader=lambda: cat, runner=runner,
                           model_probe=ready, database_probe=ready)
    app = create_app(config=cfg)
    app.dependency_overrides[get_services] = lambda: services
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, services, calls, tmp_path


def ask(client, question, session=None):
    return client.post("/api/tanya", json={"pertanyaan": question, "id_sesi": session or str(uuid4())})


def test_five_routes_and_openapi_required_fields(env):
    client, _, _, _ = env
    paths = client.app.openapi()["paths"]
    assert set(paths) == {"/api/tanya", "/api/klarifikasi", "/api/katalog", "/api/log/{id_log}", "/api/kesehatan"}
    assert set(client.app.openapi()["components"]["schemas"]["TanyaRequest"]["required"]) == {"pertanyaan", "id_sesi"}


@pytest.mark.parametrize("question,kind", [("jawab", "JAWAB"), ("ambigu", "TANYA"),
                                        *[(f"T{i}", "TAHAN") for i in range(6)]])
def test_decisions_persist_and_log_ids_are_independent(env, question, kind):
    client, services, _, _ = env
    r = ask(client, question)
    assert r.status_code == 200
    body = r.json()
    assert body["decision"]["decision"] == kind
    log = client.get("/api/log/" + body["id_log"], headers={"X-Session-ID": body["id_sesi"]})
    assert log.status_code == 200
    assert log.json()["record"]["run_id"] != body["id_log"]
    assert log.json()["record"]["decision"] == body["decision"]
    assert len(list(services.store.directory.glob(body["id_log"] + ".jsonl"))) == 1
    if kind == "TANYA":
        assert len(body["decision"]["evidence"]) == 3


def test_validation_does_not_call_pipeline_and_errors_do_not_echo_input(env):
    client, _, calls, _ = env
    secret = "/private/SYNTHETIC/traceback"
    r = client.post("/api/tanya", json={"pertanyaan": secret, "id_sesi": str(uuid4()), "sql": "SELECT 1"})
    assert r.status_code == 422 and calls == []
    assert secret not in r.text
    assert client.post("/api/tanya", content="{", headers={"Content-Type": "application/json"}).status_code == 422


def test_log_requires_session_and_hides_cross_session_existence(env):
    client, _, _, _ = env
    body = ask(client, "ambigu").json()
    url = "/api/log/" + body["id_log"]
    assert client.get(url).status_code == 422
    wrong = client.get(url, headers={"X-Session-ID": str(uuid4())})
    missing = client.get("/api/log/" + str(uuid4()), headers={"X-Session-ID": str(uuid4())})
    assert wrong.status_code == missing.status_code == 404
    assert wrong.json() == missing.json()


def test_clarification_uses_stored_evidence_is_idempotent_and_keeps_original(env):
    client, services, calls, _ = env
    body = ask(client, "ambigu").json()
    req = {k: body[k] for k in ("id_sesi", "id_log")}
    req["indikator_pilihan"] = "SYN_B"
    first = client.post("/api/klarifikasi", json=req)
    again = client.post("/api/klarifikasi", json=req)
    assert first.status_code == again.status_code == 200
    assert first.json() == again.json()
    assert first.json()["decision"]["answer"]["candidate"]["code"] == "SYN_B"
    assert len(calls) == 1
    original = services.store.read(body["id_log"])
    assert original.decision.decision == "TANYA"
    lines = (services.store.directory / (body["id_log"] + ".clarifications.jsonl")).read_text().splitlines()
    assert len(lines) == 1
    req["indikator_pilihan"] = "SYN_C"
    assert client.post("/api/klarifikasi", json=req).status_code == 409


def test_invalid_selection_and_original_state(env):
    client, _, _, _ = env
    for question, code, expected in [("ambigu", "SYN_OUTSIDE", 422), ("jawab", "SYN_A", 409)]:
        body = ask(client, question).json()
        r = client.post("/api/klarifikasi", json={"id_sesi": body["id_sesi"], "id_log": body["id_log"],
                                                  "indikator_pilihan": code})
        assert r.status_code == expected


def test_concurrent_different_choices_have_one_winner(env):
    client, services, _, _ = env
    body = ask(client, "ambigu").json()
    requests = [{"id_sesi": body["id_sesi"], "id_log": body["id_log"], "indikator_pilihan": code}
                for code in ("SYN_A", "SYN_B")]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda req: client.post("/api/klarifikasi", json=req), requests))
    assert sorted(r.status_code for r in responses) == [200, 409]
    lines = (services.store.directory / (body["id_log"] + ".clarifications.jsonl")).read_text().splitlines()
    assert len(lines) == 1


def test_catalog_and_health_distinguish_failure_from_empty(env):
    client, services, _, _ = env
    assert client.get("/api/katalog").json()["indikator"][0]["kode"] == "SYN_A"
    assert client.get("/api/kesehatan").status_code == 200
    services.model_probe = lambda: ServiceHealth(status="UNKNOWN", checked_at=None)
    health = client.get("/api/kesehatan")
    assert health.status_code == 503 and health.json()["model"]["status"] == "UNKNOWN"

    def broken():
        raise OSError("SYNTHETIC private path /secret")
    services.catalog_loader = broken
    assert client.get("/api/katalog").status_code == 503
    assert "/secret" not in client.get("/api/katalog").text


def test_failed_log_write_and_corrupt_log_are_not_success(env, monkeypatch):
    client, services, _, _ = env
    body = ask(client, "jawab").json()
    path = services.store.directory / (body["id_log"] + ".jsonl")
    path.write_text("{broken", encoding="utf-8")
    r = client.get("/api/log/" + body["id_log"], headers={"X-Session-ID": body["id_sesi"]})
    assert r.status_code == 503

    def broken(*args, **kwargs):
        raise OSError("SYNTHETIC private path /secret")
    monkeypatch.setattr(services.store, "save", broken)
    r = ask(client, "jawab")
    assert r.status_code == 503 and r.json()["error"]["id_log"] is None
    assert "/secret" not in r.text


def test_real_orchestrator_early_exit_uses_mock_without_network(env):
    from backend.app.orchestrator import run_question_with_log
    client, services, calls, _ = env
    services.runner = run_question_with_log
    services.llm = MockLlmClient(["DROP TABLE provinsi"])
    body = ask(client, "IPM").json()
    assert body["decision"]["reason_code"] == "T1"
    assert calls == []
    rec = services.store.read(body["id_log"])
    assert rec.skeletons == [] and set(rec.latency_ms) == {"s1", "s2"}


def test_health_unavailable_openapi_uses_health_payload(env):
    client, _, _, _ = env
    responses = client.app.openapi()["paths"]["/api/kesehatan"]["get"]["responses"]
    assert responses["503"]["content"]["application/json"]["schema"]["$ref"].endswith("/HealthResponse")


def test_catalog_configuration_failure_is_operational(env):
    from backend.app.config import ConfigError
    client, services, _, _ = env

    def broken():
        raise ConfigError("SYNTHETIC private configuration")
    services.catalog_loader = broken
    response = client.get("/api/katalog")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "CATALOG_UNAVAILABLE"


def test_model_probe_checks_identity_without_generating_samples(env, monkeypatch):
    import backend.app.api.routes as module
    _, services, _, _ = env
    seen = []

    class Reply:
        status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return {"data": [{"id": services.config["model"]["name"]}]}

    def fake_get(url, **kwargs):
        seen.append((url, kwargs))
        return Reply()

    monkeypatch.setattr(module.requests, "get", fake_get)
    assert module.probe_model(services.config).status == "AVAILABLE"
    assert [url for url, _ in seen] == [services.config["api"]["model_health_url"],
                                       services.config["api"]["model_list_url"]]
    assert all(args["timeout"] == services.config["api"]["health_timeout_s"] for _, args in seen)
    assert all(args["allow_redirects"] is False for _, args in seen)
    monkeypatch.setattr(Reply, "json", lambda self: {"data": [{"id": "SYNTHETIC_WRONG_MODEL"}]})
    assert module.probe_model(services.config).diagnostic_code == "MODEL_ID_MISMATCH"


def test_database_probe_uses_guard_and_readonly_executor(env, monkeypatch):
    import sqlite3
    import backend.app.api.routes as module
    _, services, _, tmp = env
    db = tmp / "synthetic.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE nilai_indikator(kode_indikator TEXT, nilai REAL)")
        conn.execute("INSERT INTO nilai_indikator VALUES ('SYN_A', 1.0)")
    services.config["execution"]["db_path"] = str(db)
    before = db.read_bytes()
    assert module.probe_database(services).status == "AVAILABLE"
    assert db.read_bytes() == before
    monkeypatch.setattr(module, "validate_sql", lambda sql: (False, "SYNTHETIC rejection"))
    assert module.probe_database(services).status == "UNKNOWN"


def test_extra_trace_is_not_silently_discarded_and_errors_are_sanitized(env):
    import json
    client, services, _, _ = env
    body = ask(client, "T0").json()
    path = services.store.directory / (body["id_log"] + ".jsonl")
    original = json.loads(path.read_text())
    original["samples"] = [{"raw_output": "SYNTHETIC"}]
    path.write_text(json.dumps(original) + "\n", encoding="utf-8")
    response = client.get("/api/log/" + body["id_log"], headers={"X-Session-ID": body["id_sesi"]})
    assert response.status_code == 503


def test_get_has_no_body_and_unexpected_error_is_safe(env):
    client, services, _, _ = env
    assert client.request("GET", "/api/katalog", json={"extra": "SYNTHETIC"}).status_code == 422
    assert client.get("/api/katalog?extra=SYNTHETIC").status_code == 422

    def broken(*args, **kwargs):
        raise RuntimeError("Traceback SYNTHETIC /private/internal")
    services.runner = broken
    response = ask(client, "jawab")
    assert response.status_code == 500
    assert "Traceback" not in response.text and "/private" not in response.text
