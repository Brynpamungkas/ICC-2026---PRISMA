"""Kondisi pembanding evaluasi K1/K2 (D10 C2; keputusan tim K-08, 20 Okt 2026). K3 = orchestrator.run_question_with_log.

Variabel bersama dengan K3: model, decoding, N (config sampling.n_samples), skema, kontrak SQL, ekstraksi S1, sqlguard,
eksekutor read-only, voting persamaan (3). Perbedaan hanya pada cara menangani tafsir:
- K1 (antarmuka biasa): model menerima DAFTAR INDIKATOR katalog dan memilih sendiri satu indikator per sampel; tanpa
  klarifikasi; jawaban = vektor hasil terbanyak. Gerbang periode/wilayah/operasi diperiksa pada indikator pilihan model.
  K(q) katalog dihitung hanya sebagai audit penautan, tidak dipakai K1 (D10 C6).
- K2 (klarifikasi katalog): TANYA bila |K(q)| > 1 SEBELUM eksekusi (tanpa bukti hasil); |K(q)| = 0 -> T1;
  |K(q)| = 1 -> jalur yang sama dengan K3.
Hanya untuk evaluasi; API/demo tetap K3."""
from __future__ import annotations

import re
import time
import uuid
from pathlib import Path

from backend.app.catalog import Catalog, get_catalog
from backend.app.config import load_config
from backend.app.llm.client import LlmClient, LlmUnavailable
from backend.app.llm.examples import load_examples
from backend.app.llm.prompt import K1_SYSTEM_PROMPT, build_k1_prompt, extraction_context
from backend.app.orchestrator import run_question_with_log
from backend.app.schemas import Decision, Evidence, ExecResult, LogRecord, SqlSkeleton
from backend.app.sqlguard.executor import DatabaseUnavailable, run_query
from backend.app.sqlguard.validator import validate_sql
from backend.app.steps.s1_extract import extract
from backend.app.steps.s2_resolve import resolve
from backend.app.steps.s3_checks import check_candidates
from backend.app.steps.s4_sample import parse_output
from backend.app.steps.s5_execute import TEXT_COLUMNS, bind_params
from backend.app.steps.s6_vote import vote
from backend.app.steps.s7_decide import no_value, tahan
from backend.app.suggest import suggestion

_CODE_LINE = re.compile(r"INDIKATOR\s*:\s*`?([A-Za-z0-9_]+)`?", re.I)
GATE_PREFIX = "GATE_"


def parse_k1_output(text: str, codes: set[str]) -> tuple[str | None, str]:
    """Split a K1 completion into (indicator code chosen by the model | None, SQL text)."""
    m = _CODE_LINE.search(text)
    code = m.group(1).upper() if m else None
    rest = (text[:m.start()] + text[m.end():]) if m else text
    return (code if code in codes else None), parse_output(rest)


def _new_record(question: str, mode: str, cfg: dict, cat: Catalog, session_id: str) -> LogRecord:
    return LogRecord(run_id=uuid.uuid4().hex, session_id=session_id, question=question, mode=mode,
                     prompt_version=str(cfg["prompt"]["version"]), dictionary_hash=cat.version)


def run_k1(question: str, *, llm=None, catalog: Catalog | None = None, db_path: str | Path | None = None,
           config: dict | None = None, session_id: str = "eval") -> tuple[Decision, LogRecord]:
    cfg = config or load_config()
    cat = catalog or get_catalog()
    rec = _new_record(question, "K1", cfg, cat, session_id)
    lat = rec.latency_ms
    t = time.perf_counter()
    ext = extract(question, catalog=cat, config=cfg)
    rec.extraction = ext
    rec.k = [c.code for c in resolve(ext, catalog=cat)]                      # audit penautan saja (D10 C6)
    lat["s1"] = round((time.perf_counter() - t) * 1000, 3)

    client = llm or LlmClient(cfg)
    rec.model_name = getattr(client, "model_name", type(client).__name__)
    codes = set(cat.indicators)
    listing = [(c, m.name, m.unit) for c, m in cat.indicators.items()]
    prompt = build_k1_prompt(question, listing, extraction_context(ext), load_examples(cfg, catalog=cat))
    t = time.perf_counter()
    try:
        raw = client.generate(prompt, cfg["sampling"]["n_samples"], system=K1_SYSTEM_PROMPT)
    except LlmUnavailable:
        d = tahan("T0", suggestion("T0", cat))
        return d, _finish(rec, d)
    finally:
        lat["s4"] = round((time.perf_counter() - t) * 1000, 3)

    chosen: list[tuple[str, str] | None] = []
    for text in raw:
        code, sql = parse_k1_output(text, codes)
        if code is None:
            rec.skeletons.append(SqlSkeleton(sql=sql, valid=False, reject_reason="kode indikator tidak dipilih/tidak dikenal"))
            chosen.append(None)
            continue
        ok, why = validate_sql(sql, forbidden_literals=codes, region_count=len(ext.regions),
                            shape=(ext.operation, ext.rank_direction, ext.top_n))
        rec.skeletons.append(SqlSkeleton(sql=f"-- INDIKATOR: {code}\n{sql}", valid=ok, reject_reason=why))
        chosen.append((code, sql) if ok else None)
    if not any(chosen):
        d = tahan("T4", suggestion("T4", cat))
        return d, _finish(rec, d)

    t = time.perf_counter()
    periods: dict[str, str | None] = {}
    per_sample: list[list[ExecResult]] = []
    try:
        for item in chosen:
            if item is None:
                continue
            code, sql = item
            cand = cat.candidate(code)
            chk = check_candidates(ext, [cand], catalog=cat, config=cfg)
            periods[code] = chk.period
            if chk.reason:
                res = ExecResult(candidate_code=code, columns=[], rows=[], structure="NUMBER", unit=cand.unit,
                                 error=GATE_PREFIX + chk.reason)
            else:
                params = bind_params(code, ext.model_copy(update={"period": chk.period}))
                q = run_query(sql, params, db_path=db_path or cfg["execution"]["db_path"])
                res = ExecResult(candidate_code=code, columns=q.columns, rows=q.rows, unit=cand.unit, error=q.error,
                                 structure="TEXT" if ext.operation == "RANK" and TEXT_COLUMNS & set(q.columns) else "NUMBER")
            per_sample.append([res])
    except DatabaseUnavailable:
        d = tahan("T0", suggestion("T0", cat))
        return d, _finish(rec, d)
    finally:
        lat["s5"] = round((time.perf_counter() - t) * 1000, 3)

    if all(r.error is None and no_value(r) for vec in per_sample for r in vec):
        d = tahan("T5", suggestion("T5", cat))
        return d, _finish(rec, d)
    votes = vote(per_sample)
    rec.votes = votes
    win = votes[0].result
    period = periods.get(win.candidate_code)
    if win.error and win.error.startswith(GATE_PREFIX):
        code = win.error[len(GATE_PREFIX):]
        d = tahan(code, suggestion(code, cat, candidates=[win.candidate_code], period=ext.period), period)
    elif win.error:
        d = tahan("T0", suggestion("T0", cat), period)
    elif no_value(win):
        d = tahan("T5", suggestion("T5", cat), period)
    else:
        d = Decision(decision="JAWAB", answer=Evidence(candidate=cat.candidate(win.candidate_code), result=win),
                     period_used=period)
    return d, _finish(rec, d)


def _finish(rec: LogRecord, d: Decision) -> LogRecord:
    rec.decision = d
    return rec


def run_k2(question: str, *, llm=None, catalog: Catalog | None = None, db_path: str | Path | None = None,
           config: dict | None = None, session_id: str = "eval", tau: dict | None = None,
           examples: list[dict] | None = None) -> tuple[Decision, LogRecord]:
    cfg = config or load_config()
    cat = catalog or get_catalog()
    ext = extract(question, catalog=cat, config=cfg)
    k = resolve(ext, catalog=cat)
    if len(k) > 1:                                    # pemicu dari K, bukan K' (D10 C2), sebelum eksekusi
        rec = _new_record(question, "K2", cfg, cat, session_id)
        rec.extraction, rec.k = ext, [c.code for c in k]
        d = Decision(decision="TANYA", evidence=[])
        return d, _finish(rec, d)
    d, rec = run_question_with_log(question, "K3", llm=llm, catalog=cat, db_path=db_path, config=cfg,
                                   session_id=session_id, tau=tau, examples=examples, _record_mode="K2")
    rec.mode = "K2"
    return d, rec


def run_condition(mode: str, question: str, **kw) -> tuple[Decision, LogRecord]:
    if mode == "K1":
        kw.pop("tau", None)
        kw.pop("examples", None)
        return run_k1(question, **kw)
    if mode == "K2":
        return run_k2(question, **kw)
    if mode == "K3":
        return run_question_with_log(question, "K3", **kw)
    raise ValueError(f"kondisi tidak dikenal: {mode}")
