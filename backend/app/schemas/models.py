"""Kontrak data antarlangkah (docs/03_DATA_CONTRACTS.md). Jangan ubah tanpa prompt Ubah Kontrak."""
from typing import Literal, Optional
from pydantic import BaseModel, Field

Operation = Literal["NONE", "SUM", "AVG", "RANK"]
Structure = Literal["TEXT", "NUMBER"]
DecisionKind = Literal["JAWAB", "TANYA", "TAHAN"]
ReasonCode = Literal["T0", "T1", "T2", "T3", "T4", "T5"]


class ExtractionResult(BaseModel):          # langkah 1
    raw_question: str
    terms: list[str]
    regions: list[str] = Field(default_factory=list)   # kode provinsi; kosong = semua
    period: Optional[str] = None                        # "YYYY-MM"; None = terbaru
    operation: Operation = "NONE"
    rank_direction: Optional[Literal["highest", "lowest"]] = None
    top_n: int = 1
    unresolved: list[str] = Field(default_factory=list)   # PROPOSED: penyebutan wilayah/periode yang tak bisa diselesaikan (-> T2, bukan 'semua provinsi')


class Candidate(BaseModel):                 # satu indikator dari katalog
    code: str
    canonical_name: str
    unit: str


class SqlSkeleton(BaseModel):               # langkah 4
    sql: str
    valid: bool
    reject_reason: Optional[str] = None


class ExecResult(BaseModel):                # langkah 5
    candidate_code: str
    columns: list[str]
    rows: list[list]                        # nilai angka sebagai float, teks sebagai str
    structure: Structure
    unit: str
    error: Optional[str] = None


class VoteResult(BaseModel):                # langkah 6
    candidate_code: str
    result: ExecResult
    votes: int
    tie: bool = False


class Evidence(BaseModel):                  # bukti pada TANYA
    candidate: Candidate
    result: ExecResult


class Decision(BaseModel):                  # langkah 7
    decision: DecisionKind
    answer: Optional[Evidence] = None       # JAWAB
    evidence: list[Evidence] = Field(default_factory=list)   # TANYA
    reason_code: Optional[ReasonCode] = None                 # TAHAN
    suggestion: Optional[str] = None
    period_used: Optional[str] = None


class LogRecord(BaseModel):                 # satu baris JSONL per pertanyaan
    run_id: str
    session_id: str
    question: str
    extraction: Optional[ExtractionResult] = None
    k: list[str] = Field(default_factory=list)
    k_prime: list[str] = Field(default_factory=list)
    skeletons: list[SqlSkeleton] = Field(default_factory=list)
    votes: list[VoteResult] = Field(default_factory=list)
    decision: Optional[Decision] = None
    mode: Literal["K1", "K2", "K3"] = "K3"
    latency_ms: dict[str, float] = Field(default_factory=dict)   # per langkah
    model_name: Optional[str] = None
    prompt_version: Optional[str] = None
    dictionary_hash: Optional[str] = None
