"""Read-only verification of the agreed two-human annotation evidence.

The file checks cannot prove a human acted independently. The named reviewer
attests that fact; both initial files and their pre-reconciliation agreement
must still be retained and match the hashes supplied by the team.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

from backend.app.config import ROOT
from scripts import dataset_tools as dt


def validate_protocol(path: Path, question_ids: set[str]) -> dict:
    try:
        protocol = json.loads(path.read_text(encoding="utf-8"))
        if not str(protocol.get("reviewer") or "").strip():
            raise ValueError("peninjau manusia belum ditetapkan")
        if protocol.get("initial_labels_locked_before_reconciliation") is not True:
            raise ValueError("label awal belum dikunci sebelum rekonsiliasi")
        if protocol.get("llm_draft_opened_after_initial_lock") is not True:
            raise ValueError("paparan draf LLM sebelum penguncian label perlu diselesaikan")
        artifacts = {}
        for key in ("initial_a", "initial_b", "agreement_report", "reconciliation_log"):
            entry = protocol[key]
            file = ROOT / entry["path"]
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            if digest != entry["sha256"]:
                raise ValueError(f"hash bukti {key} berbeda")
            artifacts[key] = file
        if artifacts["initial_a"].resolve() == artifacts["initial_b"].resolve():
            raise ValueError("dua penilai memerlukan dua berkas awal berbeda")
        initial = [dt.read_csv(artifacts[k], dt.L_COLS) for k in ("initial_a", "initial_b")]
        annotators = [{r["annotator_id"] for r in rows} for rows in initial]
        if any(len(ids) != 1 or "" in ids for ids in annotators) or annotators[0] == annotators[1]:
            raise ValueError("dua penilai manusia harus memiliki ID yang berbeda")
        groups = [dt.group_labels(rows) for rows in initial]
        for group in groups:
            for qid in question_ids:
                items = group.get(qid) or []
                if not items or any(r["verification_status"] != "VERIFIED" or not r["reference_sql"] for r in items):
                    raise ValueError(f"label awal penilai belum lengkap untuk {qid}")
                if len({r["decision_reference"] for r in items}) != 1:
                    raise ValueError(f"label keputusan penilai tidak konsisten untuk {qid}")
        decisions = [{q: items[0]["decision_reference"] for q, items in g.items()} for g in groups]
        measured = dt.cohen_kappa(*decisions)
        report = json.loads(artifacts["agreement_report"].read_text(encoding="utf-8"))
        if report.get("N") != measured["N"] or report.get("contingency_A_rows_B_cols") != measured["contingency_A_rows_B_cols"]:
            raise ValueError("laporan kappa tidak cocok dengan dua label awal")
        for key in ("Po", "Pe", "kappa"):
            a, b = report.get(key), measured.get(key)
            if (a is None) != (b is None) or (a is not None and not math.isclose(a, b)):
                raise ValueError("angka kesepakatan awal tidak cocok")
        if not artifacts["reconciliation_log"].read_text(encoding="utf-8").strip():
            raise ValueError("catatan rekonsiliasi belum tersedia")
        return {"reviewer": protocol["reviewer"], "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "initial_annotators": [next(iter(a)) for a in annotators], "agreement_N": measured["N"],
                "limitations": "Independensi dan urutan kerja tetap memerlukan audit manusia."}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"Bukti protokol dua penilai belum sah: {exc}") from exc


def validate_annotation_evidence(evaluation: dict, question_ids: set[str], *, label_path: Path | None = None,
                                 db_path: Path | None = None) -> dict:
    """Keep independent annotation and the explicitly approved M5 alternative distinct."""
    method = evaluation.get('annotation_method', 'two_independent_humans')
    if method == 'two_independent_humans':
        result = validate_protocol(ROOT / evaluation['annotation_protocol'], question_ids)
        return {**result, 'method': method, 'paper_independent_annotation_claimed': True,
                'artifact_path': evaluation['annotation_protocol']}
    if method != 'llm_draft_human_review':
        raise SystemExit('Metode anotasi tidak dikenal; jangan memilih jalur lain otomatis.')
    try:
        path = ROOT / evaluation['annotation_review']
        review = json.loads(path.read_text(encoding='utf-8'))
        if review['method'] != method:
            raise ValueError('metode catatan review tidak cocok')
        approval = review['approval']
        if approval.get('human_approval_reported') is not True or not approval.get('reporter') or not approval.get('statement'):
            raise ValueError('persetujuan manusia belum dicatat')
        if datetime.fromisoformat(approval['recorded_at']).tzinfo is None:
            raise ValueError('waktu pencatatan persetujuan perlu zona waktu')
        if review.get('kappa') is not None or review.get('independent_initial_labels_claimed') is not False:
            raise ValueError('jalur M5 ini tidak boleh mengklaim kappa/label awal independen yang tidak tersedia')
        ids = review['question_ids']
        if len(ids) != len(set(ids)) or not question_ids <= set(ids):
            raise ValueError('cakupan pertanyaan melampaui review manusia')
        artifacts = {}
        for key in ('labels_final', 'draft_llm', 'reference_answers', 'database', 'catalog_version', 'questions'):
            entry = review['artifacts'][key]
            file = ROOT / entry['path']
            if hashlib.sha256(file.read_bytes()).hexdigest() != entry['sha256']:
                raise ValueError(f'hash {key} berbeda dari catatan review')
            artifacts[key] = file
        if label_path is not None and artifacts['labels_final'].resolve() != label_path.resolve():
            raise ValueError('berkas label berbeda dari yang disetujui')
        if db_path is not None and artifacts['database'].resolve() != db_path.resolve():
            raise ValueError('snapshot database berbeda dari jawaban rujukan')
        rows = dt.read_csv(artifacts['labels_final'], dt.L_COLS)
        if {r['question_id'] for r in rows} != set(ids) or any(
                r['verification_status'] != 'VERIFIED' or not r['reference_sql'] for r in rows):
            raise ValueError('label final belum lengkap/VERIFIED dalam cakupan review')
        return {'method': method, 'reviewer': approval['reporter'], 'approval_source': 'user_reported_human_review',
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'artifact_path': str(path.relative_to(ROOT)),
                'kappa': None, 'paper_independent_annotation_claimed': False,
                'limitations': 'Draf LLM disetujui manusia menurut pernyataan pengguna; bukan dua label awal independen/kappa paper.'}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f'Bukti review M5 belum sah: {exc}') from exc
