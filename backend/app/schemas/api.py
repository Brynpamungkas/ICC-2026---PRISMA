"""Approved API boundary contracts; internal M1/M2 models remain unchanged."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, StrictStr, model_validator

from backend.app.schemas.models import Decision, LogRecord


def uuid4_text(value: str) -> str:
    parsed = UUID(value)
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError("a canonical UUIDv4 is required")
    return value


def nonempty(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("a nonempty string is required")
    return value


SessionId = Annotated[StrictStr, AfterValidator(uuid4_text)]
Nonempty = Annotated[StrictStr, AfterValidator(nonempty)]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class TanyaRequest(ApiModel):
    pertanyaan: Nonempty
    id_sesi: SessionId


class ClarifyRequest(ApiModel):
    id_sesi: SessionId
    id_log: SessionId
    indikator_pilihan: Nonempty


class ApiDecision(Decision):
    model_config = ApiModel.model_config

    @model_validator(mode="after")
    def validate_branch(self) -> ApiDecision:
        if self.decision == "JAWAB":
            if self.answer is None or self.evidence or self.reason_code is not None:
                raise ValueError("invalid JAWAB branch")
            if not self.period_used:
                raise ValueError("an answer requires its actual period")
        elif self.decision == "TANYA":
            if self.answer is not None or len(self.evidence) < 2 or self.reason_code is not None:
                raise ValueError("invalid TANYA branch")
            if not self.period_used:
                raise ValueError("evidence requires its actual period")
        elif self.answer is not None or self.evidence or self.reason_code is None or not self.suggestion or not self.suggestion.strip():
            raise ValueError("invalid TAHAN branch")
        items = [self.answer] if self.answer is not None else self.evidence
        if len({e.candidate.code for e in items}) != len(items):
            raise ValueError("duplicate evidence candidates")
        for item in items:
            candidate, result = item.candidate, item.result
            if candidate.code != result.candidate_code or candidate.unit != result.unit or result.error is not None:
                raise ValueError("evidence correspondence or execution failure")
            labels = {i for i, c in enumerate(result.columns) if c in {"wilayah", "periode"}}   # label baris (Tabel VII, 21 Okt)
            for row in result.rows:
                if len(row) != len(result.columns):
                    raise ValueError("row and column dimensions differ")
                for i, value in enumerate(row):
                    if value is not None and not isinstance(value, (str, int, float)):
                        raise ValueError("unsupported SQL cell type")
                    if isinstance(value, float) and not math.isfinite(value):
                        raise ValueError("nonfinite SQL value")
                    if (result.structure == "NUMBER" and i not in labels and value is not None
                            and (isinstance(value, bool) or not isinstance(value, (int, float)))):
                        raise ValueError("numeric results must contain original numbers")
        return self


class QuestionResponse(ApiModel):
    id_sesi: SessionId
    id_log: SessionId
    decision: ApiDecision


class IndicatorMetadata(ApiModel):
    kode: Nonempty
    nama_kanonik: Nonempty
    definisi_resmi: Nonempty
    satuan: Nonempty
    sumber: Nonempty
    cakupan_wilayah: list[StrictStr]
    periode_tersedia: list[StrictStr]


class CatalogResponse(ApiModel):
    indikator: list[IndicatorMetadata]


class LogResponse(ApiModel):
    id_log: SessionId
    record: LogRecord


class ServiceHealth(ApiModel):
    status: Literal["AVAILABLE", "UNAVAILABLE", "UNKNOWN"]
    checked_at: str | None
    diagnostic_code: str | None = None

    @model_validator(mode="after")
    def validate_time(self) -> ServiceHealth:
        if self.checked_at is not None:
            parsed = datetime.fromisoformat(self.checked_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("health timestamps require a timezone")
        if self.status == "AVAILABLE" and self.checked_at is None:
            raise ValueError("availability requires an actual probe timestamp")
        return self


class HealthResponse(ApiModel):
    model: ServiceHealth
    database: ServiceHealth


class ErrorDetail(ApiModel):
    code: str
    message: str
    id_log: SessionId | None


class HttpErrorResponse(ApiModel):
    error: ErrorDetail


class ClarificationEvent(ApiModel):
    event_id: SessionId
    id_sesi: SessionId
    id_log: SessionId
    indikator_pilihan: Nonempty
    selected_at: str
    decision: ApiDecision

    @model_validator(mode="after")
    def validate_choice(self) -> ClarificationEvent:
        if self.decision.decision != "JAWAB" or self.decision.answer.candidate.code != self.indikator_pilihan:
            raise ValueError("clarification event must answer the selected evidence")
        if datetime.fromisoformat(self.selected_at).tzinfo is None:
            raise ValueError("clarification timestamps require a timezone")
        return self
