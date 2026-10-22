"""Algoritma 1 utuh. Satu fungsi publik untuk antarmuka dan evaluator.
mode: "K1" (tanpa klarifikasi), "K2" (tanya bila |K(q)| > 1), "K3" (PRISMA penuh).

M2: hanya K3. K1/K2 adalah pembanding evaluasi (M5, K-08 OPEN) dan sengaja belum diimplementasikan di sini.
Urutan gerbang mengikuti Algoritma 1: T1 -> T2/T3 -> T4 -> T5 -> voting -> kesetaraan. Pada T1-T3 model TIDAK dipanggil dan
langkah yang dilewati tidak dicatat latensinya. Kegagalan model/DB -> TAHAN T0 (nama kode K-06 masih OPEN)."""
from __future__ import annotations

import time
import uuid
from pathlib import Path

from backend.app.catalog import Catalog, get_catalog
from backend.app.config import ConfigError, load_config, load_tau
from backend.app.llm.client import LlmClient, LlmUnavailable
from backend.app.llm.examples import load_examples
from backend.app.logging.jsonl import write_log
from backend.app.schemas import Decision, Evidence, ExtractionResult, LogRecord
from backend.app.sqlguard.executor import DatabaseUnavailable
from backend.app.steps.s1_extract import extract
from backend.app.steps.s2_resolve import resolve
from backend.app.steps.s3_checks import check_candidates
from backend.app.steps.s4_sample import sample_skeletons
from backend.app.steps.s5_execute import execute_all
from backend.app.steps.s6_vote import vote
from backend.app.steps.s7_decide import decide, no_value, tahan
from backend.app.suggest import suggestion


def _tau(config: dict) -> dict:
    try:
        return load_tau(config["decision"]["tau_u_file"])
    except ConfigError:
        import yaml
        from backend.app.config import ROOT
        with open(ROOT / config["decision"]["tau_u_file"], encoding="utf-8") as f:
            return yaml.safe_load(f)        # nilai null tetap null: S7 memakai tau hanya bila perlu dan menolak null


def run_question_with_log(question: str, mode: str = "K3", *, llm=None, catalog: Catalog | None = None,
                          db_path: str | Path | None = None, config: dict | None = None, session_id: str = "local",
                          log_path: str | None = None, tau: dict | None = None, examples: list[dict] | None = None
                          ) -> tuple[Decision, LogRecord]:
    if mode != "K3":
        raise NotImplementedError("Hanya K3 yang tersedia (K1/K2 = pembanding evaluasi, M5)")
    cfg = config or load_config()
    cat = catalog or get_catalog()
    rec = LogRecord(run_id=uuid.uuid4().hex, session_id=session_id, question=question, mode="K3",
                    prompt_version=str(cfg["prompt"]["version"]), dictionary_hash=cat.version)
    lat: dict[str, float] = rec.latency_ms

    def timed(name, fn, *a, **kw):
        t0 = time.perf_counter()
        try:
            return fn(*a, **kw)
        finally:
            lat[name] = round((time.perf_counter() - t0) * 1000, 3)

    def finish(d: Decision) -> tuple[Decision, LogRecord]:
        rec.decision = d
        if log_path is None and cfg["logging"].get("path"):
            pass                                    # log ditulis hanya bila diminta (evaluator/API), bukan di setiap tes
        if log_path:
            write_log(rec, log_path)
        return d, rec

    ext: ExtractionResult = timed("s1", extract, question, catalog=cat, config=cfg)
    rec.extraction = ext
    k = timed("s2", resolve, ext, catalog=cat)
    rec.k = [c.code for c in k]
    if not k:
        return finish(tahan("T1", suggestion("T1", cat)))

    chk = timed("s3", check_candidates, ext, k, catalog=cat, config=cfg)
    rec.k_prime = [c.code for c in chk.k_prime]
    if chk.reason:
        return finish(tahan(chk.reason, suggestion(chk.reason, cat, candidates=[c.code for c in k], unresolved=ext.unresolved,
                                                   period=ext.period), None))
    period = chk.period
    ext = ext.model_copy(update={"period": period})
    rec.extraction = ext
    kp = chk.k_prime

    client = llm or LlmClient(cfg)
    rec.model_name = getattr(client, "model_name", type(client).__name__)
    try:
        skeletons = timed("s4", sample_skeletons, question, ext, cfg["sampling"]["n_samples"], llm=client, catalog=cat,
                          examples=load_examples(cfg) if examples is None else examples)
    except LlmUnavailable:
        return finish(tahan("T0", suggestion("T0", cat), period))
    rec.skeletons = skeletons
    if not any(s.valid for s in skeletons):
        return finish(tahan("T4", suggestion("T4", cat), period))

    try:
        per_skeleton = timed("s5", execute_all, skeletons, kp, ext, db_path=db_path or cfg["execution"]["db_path"], catalog=cat)
    except DatabaseUnavailable:
        return finish(tahan("T0", suggestion("T0", cat), period))
    if all(r.error is None and no_value(r) for vec in per_skeleton for r in vec):          # semua hasil tanpa nilai (ALG-19, K-16)
        return finish(tahan("T5", suggestion("T5", cat), period))

    votes = timed("s6", vote, per_skeleton)
    rec.votes = votes
    if votes and all(v.result.error is None and no_value(v.result) for v in votes):     # K-16: pemenang tanpa nilai
        return finish(tahan("T5", suggestion("T5", cat), period))
    cands = {c.code: c for c in kp}
    d = timed("s7", decide, votes, tau if tau is not None else _tau(cfg), candidates=cands, period_used=period)
    return finish(d)


def run_question(question: str, mode: str = "K3", **kwargs) -> Decision:
    return run_question_with_log(question, mode, **kwargs)[0]


def clarify(decision: Decision, candidate_code: str) -> Decision:
    """K-11: ambil jawaban kandidat pilihan dari bukti tersimpan, tanpa memanggil model lagi."""
    if decision.decision != "TANYA":
        raise ValueError("klarifikasi hanya untuk keputusan TANYA")
    chosen: Evidence | None = next((e for e in decision.evidence if e.candidate.code == candidate_code), None)
    if chosen is None:
        raise ValueError(f"kandidat {candidate_code!r} tidak ada pada bukti")
    return Decision(decision="JAWAB", answer=chosen, period_used=decision.period_used)
