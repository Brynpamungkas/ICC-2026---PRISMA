"""Five application endpoints, filesystem evidence, and injected CPU-test services."""
from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Annotated, Protocol
from uuid import uuid4

import requests
from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import ValidationError

from backend.app.catalog import Catalog, get_catalog
from backend.app.config import ConfigError
from backend.app.orchestrator import clarify, run_question_with_log
from backend.app.schemas import Decision, LogRecord
from backend.app.schemas.api import (
    ApiDecision, CatalogResponse, ClarificationEvent, ClarifyRequest, HealthResponse,
    IndicatorMetadata, LogResponse, QuestionResponse, ServiceHealth, SessionId,
    TanyaRequest, uuid4_text,
)
from backend.app.sqlguard.executor import run_query
from backend.app.sqlguard.validator import validate_sql


class LlmLike(Protocol):
    def generate(self, prompt: str, n: int) -> list[str]: ...


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, code: str, message: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message


@dataclass
class LogStore:
    directory: Path

    def _path(self, id_log: str, *, event: bool = False) -> Path:
        uuid4_text(id_log)
        suffix = ".clarifications.jsonl" if event else ".jsonl"
        return self.directory / (id_log + suffix)

    def _publish(self, path: Path, payload: str) -> None:
        """Publish one complete immutable JSONL record without replacing an existing one."""
        self.directory.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".pending-", dir=self.directory)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(payload + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def save(self, id_log: str, record: LogRecord) -> None:
        self._publish(self._path(id_log), record.model_dump_json())

    def read(self, id_log: str) -> LogRecord:
        lines = self._path(id_log).read_text(encoding="utf-8").splitlines()
        if len(lines) != 1:
            raise ValueError("expected one original question record")
        payload = json.loads(lines[0])
        if not isinstance(payload, dict) or set(payload) - set(LogRecord.model_fields):
            raise ValueError("unsupported trace schema; do not silently discard fields")
        record = LogRecord.model_validate(payload)
        if record.decision is not None:
            ApiDecision.model_validate(record.decision.model_dump())
        return record

    def select(self, event: ClarificationEvent) -> ClarificationEvent:
        path = self._path(event.id_log, event=True)
        try:
            self._publish(path, event.model_dump_json())
            return event
        except FileExistsError:
            lines = path.read_text(encoding="utf-8").splitlines()
            if len(lines) != 1:
                raise ValueError("invalid clarification event")
            stored = ClarificationEvent.model_validate_json(lines[0])
            if stored.id_sesi != event.id_sesi or stored.id_log != event.id_log:
                raise ValueError("invalid event correlation")
            if stored.indikator_pilihan != event.indikator_pilihan:
                raise ApiError(HTTPStatus.CONFLICT, "CHOICE_CONFLICT", "Pilihan sebelumnya sudah tercatat.")
            if stored.decision.model_dump() != event.decision.model_dump():
                raise ValueError("stored choice differs from original evidence")
            return stored


@dataclass
class ApiServices:
    config: dict
    store: LogStore
    catalog_loader: Callable[[], Catalog] = get_catalog
    runner: Callable[..., tuple[Decision, LogRecord]] = run_question_with_log
    llm: LlmLike | None = None
    model_probe: Callable[[], ServiceHealth] | None = None
    database_probe: Callable[[], ServiceHealth] | None = None

    def catalog(self) -> Catalog:
        try:
            return self.catalog_loader()
        except (OSError, ValueError, KeyError, ConfigError) as exc:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, "CATALOG_UNAVAILABLE",
                           "Katalog belum dapat dibaca.") from exc


def get_services(request: Request) -> ApiServices:
    return request.app.state.api_services


def _checked(status: str, code: str | None = None) -> ServiceHealth:
    return ServiceHealth(status=status, checked_at=datetime.now(timezone.utc).isoformat(), diagnostic_code=code)


def probe_model(config: dict) -> ServiceHealth:
    api = config["api"]
    try:
        health = requests.get(api["model_health_url"], timeout=api["health_timeout_s"], allow_redirects=False)
        if health.status_code != HTTPStatus.OK:
            return _checked("UNAVAILABLE", "MODEL_UNAVAILABLE")
        models = requests.get(api["model_list_url"], timeout=api["health_timeout_s"], allow_redirects=False)
        models.raise_for_status()
        identities = {item["id"] for item in models.json()["data"]}
        if config["model"]["name"] not in identities:
            return _checked("UNAVAILABLE", "MODEL_ID_MISMATCH")
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return _checked("UNAVAILABLE", "MODEL_UNAVAILABLE")
    return _checked("AVAILABLE")


def probe_database(services: ApiServices) -> ServiceHealth:
    """Probe a real catalog indicator through the existing guard and read-only executor."""
    try:
        cat = services.catalog_loader()
        if not cat.indicators:
            return _checked("UNAVAILABLE", "CATALOG_EMPTY")
        sql = "SELECT COUNT(n.nilai) AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:indikator"
        valid, _ = validate_sql(sql)
        if not valid:
            return _checked("UNKNOWN", "PROBE_NOT_VALIDATED")
        result = run_query(sql, {"indikator": next(iter(cat.indicators))},
                           db_path=services.config["execution"]["db_path"],
                           timeout_s=services.config["execution"]["timeout_s"],
                           max_rows=services.config["execution"]["max_rows"])
        if result.error or not result.rows or not result.rows[0][0]:
            return _checked("UNAVAILABLE", "DATABASE_UNAVAILABLE")
    except Exception:
        return _checked("UNAVAILABLE", "DATABASE_UNAVAILABLE")
    return _checked("AVAILABLE")


def _read_owned(services: ApiServices, id_log: str, session: str) -> LogRecord:
    try:
        record = services.store.read(id_log)
    except FileNotFoundError as exc:
        raise ApiError(HTTPStatus.NOT_FOUND, "LOG_NOT_FOUND", "Log tidak ditemukan.") from exc
    except (OSError, ValueError, ValidationError) as exc:
        raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, "LOG_UNAVAILABLE", "Log belum dapat dibaca.") from exc
    if record.session_id != session:
        raise ApiError(HTTPStatus.NOT_FOUND, "LOG_NOT_FOUND", "Log tidak ditemukan.")
    return record


def _reject_query(request: Request) -> None:
    if request.query_params:
        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "INVALID_REQUEST", "Parameter permintaan tidak valid.")


def create_router() -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(_reject_query)])

    @router.post("/tanya", response_model=QuestionResponse)
    def tanya(body: TanyaRequest, services: Annotated[ApiServices, Depends(get_services)]) -> QuestionResponse:
        try:
            decision, record = services.runner(body.pertanyaan, mode="K3", llm=services.llm,
                                              catalog=services.catalog(), config=services.config,
                                              session_id=body.id_sesi, log_path=None)
        except ConfigError as exc:                 # mis. tau_u belum dikalibrasi (sebelum eval_lengkap.sh dev): 503, bukan 500
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, "CONFIG_INCOMPLETE",
                           "Konfigurasi layanan belum lengkap. Hubungi pengelola PRISMA.") from exc
        if (record.session_id != body.id_sesi or record.question != body.pertanyaan or record.decision is None
                or record.decision.model_dump() != decision.model_dump()):
            raise ValueError("pipeline record correlation failed")
        result = QuestionResponse(id_sesi=body.id_sesi, id_log=str(uuid4()),
                                  decision=ApiDecision.model_validate(decision.model_dump()))
        try:
            services.store.save(result.id_log, record)
        except (OSError, ValueError) as exc:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, "LOG_UNAVAILABLE",
                           "Hasil belum dapat disimpan. Permintaan belum berhasil.") from exc
        return result

    @router.post("/klarifikasi", response_model=QuestionResponse)
    def klarifikasi(body: ClarifyRequest, services: Annotated[ApiServices, Depends(get_services)]) -> QuestionResponse:
        record = _read_owned(services, body.id_log, body.id_sesi)
        if record.decision is None or record.decision.decision != "TANYA":
            raise ApiError(HTTPStatus.CONFLICT, "INVALID_STATE", "Log asal bukan keputusan TANYA.")
        if body.indikator_pilihan not in {item.candidate.code for item in record.decision.evidence}:
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "INVALID_SELECTION", "Pilihan tidak ada pada bukti.")
        decision = clarify(record.decision, body.indikator_pilihan)
        event = ClarificationEvent(event_id=str(uuid4()), id_sesi=body.id_sesi, id_log=body.id_log,
                                   indikator_pilihan=body.indikator_pilihan,
                                   selected_at=datetime.now(timezone.utc).isoformat(),
                                   decision=ApiDecision.model_validate(decision.model_dump()))
        try:
            chosen = services.store.select(event)
        except (OSError, ValueError) as exc:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, "LOG_UNAVAILABLE",
                           "Pilihan belum dapat disimpan.") from exc
        return QuestionResponse(id_sesi=body.id_sesi, id_log=body.id_log, decision=chosen.decision)

    @router.get("/katalog", response_model=CatalogResponse)
    def katalog(services: Annotated[ApiServices, Depends(get_services)]) -> CatalogResponse:
        try:
            return CatalogResponse(indikator=[
                IndicatorMetadata(kode=m.code, nama_kanonik=m.name, definisi_resmi=m.definition,
                                  satuan=m.unit, sumber=m.source, cakupan_wilayah=sorted(m.regions),
                                  periode_tersedia=sorted(m.periods))
                for m in services.catalog().indicators.values()
            ])
        except ValidationError as exc:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, "CATALOG_UNAVAILABLE",
                           "Metadata katalog belum dapat digunakan.") from exc

    @router.get("/log/{id_log}", response_model=LogResponse)
    def log(id_log: SessionId, services: Annotated[ApiServices, Depends(get_services)],
            session: Annotated[SessionId, Header(alias="X-Session-ID")]) -> LogResponse:
        record = _read_owned(services, id_log, session).model_copy(deep=True)
        for vote in record.votes:
            if vote.result.error:
                category = vote.result.error.split(":", 1)[0]
                vote.result.error = category if category in {"SQL_ERROR", "TIMEOUT", "TRUNCATED", "SERVICE_ERROR"} else "EXECUTION_ERROR"
        return LogResponse(id_log=id_log, record=record)

    @router.get("/kesehatan", response_model=HealthResponse,
                responses={HTTPStatus.SERVICE_UNAVAILABLE: {"model": HealthResponse}})
    def kesehatan(response: Response, services: Annotated[ApiServices, Depends(get_services)]) -> HealthResponse:
        def safe(probe: Callable[[], ServiceHealth]) -> ServiceHealth:
            try:
                return ServiceHealth.model_validate(probe().model_dump())
            except Exception:
                return _checked("UNAVAILABLE", "PROBE_FAILED")
        model = safe(services.model_probe or (lambda: probe_model(services.config)))
        database = safe(services.database_probe or (lambda: probe_database(services)))
        if model.status != "AVAILABLE" or database.status != "AVAILABLE":
            response.status_code = HTTPStatus.SERVICE_UNAVAILABLE
        return HealthResponse(model=model, database=database)

    return router
