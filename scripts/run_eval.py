"""Evaluasi K1/K2/K3 (D10): jalankan himpunan dev/test, kalibrasi tau di dev (replay tanpa model), hitung metrik.

  # 1) dev, K3, tau sementara 0 (hanya untuk kalibrasi replay; bukan hasil):
  python scripts/run_eval.py run --kondisi K3 --split dev --split-file eval/testset/split_seed-X.json --tau-nol
  # 2) simpan kandidat kalibrasi untuk review (belum membekukan tau):
  python scripts/run_eval.py kalibrasi eval/runs/<run_dev>
  # 3) setelah review manusia, pembekuan dan hash lengkap, jalankan test tiga kondisi:
  python scripts/run_eval.py run --kondisi K1 K2 K3 --split test --split-file eval/testset/split_seed-X.json
  # 4) metrik:
  python scripts/run_eval.py metrik eval/runs/<run_test>

Label: eval/annotations/label_final.csv + label_final.answers.jsonl (dari `dataset_tools.py cek-label`).
Semua keluaran ke eval/runs/<run_id>/ (manifest.json, <kondisi>.jsonl, metrik_<kondisi>.json).
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import os
import platform
import hashlib
import itertools
import json
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import dataset_tools as dt  # noqa: E402
from backend.app import eval_metrics as em  # noqa: E402
from backend.app.config import ConfigError, load_config, load_tau  # noqa: E402

ANN = ROOT / "eval" / "annotations"


def _sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _git() -> dict:
    def run(*a):
        try:
            return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
        except OSError:
            return None
    return {"commit": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain"))}


def load_labels(label_csv: Path, questions_csv: Path, required_ids: set[str] | None = None) -> dict[str, dict]:
    qs = {r["question_id"]: r for r in dt.read_csv(questions_csv, dt.Q_COLS)}
    rows = dt.read_csv(label_csv, dt.L_COLS)
    if required_ids is not None:
        rows = [r for r in rows if r["question_id"] in required_ids]
    wanted = required_ids if required_ids is not None else set(qs)
    present = {r["question_id"] for r in rows}
    if wanted - present or any(r["verification_status"] != "VERIFIED" for r in rows):
        raise SystemExit("Label final harus lengkap dan VERIFIED oleh manusia; DRAFT bukan ground truth.")
    from backend.app.catalog import get_catalog
    errors = dt.check_labels(rows, wanted, set(get_catalog().indicators))
    if errors:
        raise SystemExit("Label final tidak sah: " + "; ".join(errors[:5]))
    ans_path = label_csv.with_suffix(".answers.jsonl")
    if not ans_path.exists():
        raise SystemExit(f"{ans_path.name} belum ada: jalankan dataset_tools.py cek-label {label_csv}")
    answers = {(a["question_id"], a["interpretation_id"]): a
               for a in (json.loads(x) for x in ans_path.read_text(encoding="utf-8").splitlines() if x.strip())}
    labels: dict[str, dict] = {}
    for qid, items in dt.group_labels(rows).items():
        refs = []
        for r in items:
            a = answers.get((qid, r["interpretation_id"]))
            if a is None or a.get("reference_sql") != r["reference_sql"] or a.get("error"):
                raise SystemExit(f"{qid}/{r['interpretation_id']}: jawaban rujukan belum dieksekusi (cek-label ulang)")
            refs.append({"rows": a["rows"], "error": a["error"], "period": r["period"], "operation": r["operation"]})
        labels[qid] = {"y": items[0]["decision_reference"], "group": items[0]["question_group"],
                       "domain": qs[qid]["domain"] if qid in qs else "?", "refs": refs,
                       "indicator_codes": sorted({r["indicator_code"] for r in items})}
    return labels


def record_from(qid: str, domain: str, mode: str, d, rec, latency_ms: float, error: str | None) -> dict:
    ans = d.answer if d is not None else None
    return {"question_id": qid, "domain": domain, "condition": mode,
            "decision": d.decision if d is not None else None, "reason_code": d.reason_code if d is not None else None,
            "period_used": d.period_used if d is not None else None,
            "answer_candidate": ans.candidate.code if ans else None, "answer_columns": ans.result.columns if ans else None,
            "answer_rows": ans.result.rows if ans else None, "answer_error": ans.result.error if ans else None,
            "k": rec.k if rec is not None else [], "latency_ms": latency_ms, "error": error,
            "log": rec.model_dump(mode="json") if rec is not None else None}


def cmd_run(a) -> int:
    from backend.app.conditions import run_condition
    cfg = load_config()
    split = json.loads(a.split_file.read_text(encoding="utf-8"))
    ids = split[a.split]
    qs = {r["question_id"]: r for r in dt.read_csv(a.pertanyaan, dt.Q_COLS)}
    missing = [i for i in ids if i not in qs]
    if missing:
        raise SystemExit(f"ID split tidak ada di {a.pertanyaan.name}: {missing[:5]}")
    if len(ids) != len(set(ids)) or set(split["dev"]) & set(split["test"]) or set(split["dev"]) | set(split["test"]) != set(qs):
        raise SystemExit("Split harus unik, terpisah, dan mencakup corpus yang sama.")
    if split.get("inputs", {}).get(a.pertanyaan.name) != _sha(a.pertanyaan):
        raise SystemExit("Hash pertanyaan berbeda dari split; jangan membentuk ulang split diam-diam.")
    load_labels(a.label_final, a.pertanyaan, set(ids))
    from scripts.eval_protocol import validate_annotation_evidence
    protocol = validate_annotation_evidence(cfg["evaluation"], set(ids), label_path=a.label_final,
                                             db_path=ROOT / cfg["execution"]["db_path"])
    if a.split == "test":
        freeze_path = ROOT / cfg["evaluation"]["freeze_file"]
        if not freeze_path.is_file():
            raise SystemExit("Bukti pembekuan test belum tersedia; jangan menjalankan test final.")
        freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
        if not freeze.get("reviewer") or freeze.get("code_commit") != _git()["commit"] or _git()["dirty"]:
            raise SystemExit("Pembekuan memerlukan review manusia dan commit bersih yang sama.")
        required = [ROOT / os.environ.get("PRISMA_CONFIG", "config/config.yaml"),
                    ROOT / cfg["decision"]["tau_u_file"], a.pertanyaan, a.split_file, a.label_final,
                    ROOT / protocol["artifact_path"], ROOT / "backend/app/llm/prompt.py"]
        if any(freeze.get("file_sha256", {}).get(str(p.resolve().relative_to(ROOT))) != _sha(p) for p in required):
            raise SystemExit("Hash artefak test berbeda dari pembekuan.")
    if a.tau_nol:
        if a.split != "dev":
            raise SystemExit("--tau-nol hanya untuk run dev kalibrasi")
        import yaml
        tau = {u: 0.0 for u in yaml.safe_load((ROOT / cfg["decision"]["tau_u_file"]).read_text(encoding="utf-8"))}
    else:
        try:
            tau = load_tau(cfg["decision"]["tau_u_file"])
        except ConfigError as exc:
            raise SystemExit(f"{exc}. Kalibrasi di dev dulu (perintah kalibrasi), atau --tau-nol untuk run dev.")
    if getattr(a, 'check_only', False):
        print(f"READY: {len(ids)} soal {a.split}, metode anotasi {protocol['method']}; model belum dipanggil.")
        print(protocol.get('limitations', ''))
        return 0
    run_id = a.nama or f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{a.split}_{'-'.join(a.kondisi)}"
    if Path(run_id).name != run_id or run_id in {".", ".."}:
        raise SystemExit("Nama run harus satu komponen direktori.")
    out = ROOT / "eval" / "runs" / run_id
    out.mkdir(parents=True, exist_ok=False)
    cfg = deepcopy(cfg)
    cfg["transport"]["trace_dir"] = str(out / "transport")
    cfg["logging"]["trace_dir"] = str(out / "pipeline")
    (out / "resolved_config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    manifest = {"question_ids": ids, "annotation_protocol": protocol,
                "runtime": {"backend": cfg["model"]["backend"], "platform": platform.platform(), "python": platform.python_version()},
                "resolved_config_sha256": _sha(out / "resolved_config.json"),
                "run_id": run_id, "split": a.split, "conditions": a.kondisi, "n_questions": len(ids),
                "tau": tau, "tau_purpose": "kalibrasi_replay_saja" if a.tau_nol else ("beku_test" if a.split == "test" else "dev"),
                "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git": _git(),
                "model": cfg["model"]["name"], "model_digest": cfg["model"].get("digest"),
                "prompt_version": str(cfg["prompt"]["version"]), "sampling": cfg["sampling"],
                "hashes": {"config": _sha(ROOT / os.environ.get("PRISMA_CONFIG", "config/config.yaml")),
                           "tau_file": _sha(ROOT / cfg["decision"]["tau_u_file"]),
                           "db": _sha(ROOT / cfg["execution"]["db_path"]),
                           "catalog_version": (ROOT / cfg["catalog"]["dir"] / "VERSION").read_text(encoding="utf-8").strip()
                           if (ROOT / cfg["catalog"]["dir"] / "VERSION").exists() else None,
                           "split_file": _sha(a.split_file), "questions": _sha(a.pertanyaan),
                           "labels_final": _sha(a.label_final), "reference_answers": _sha(a.label_final.with_suffix('.answers.jsonl')),
                           "annotation_evidence": _sha(ROOT / protocol['artifact_path'])}}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for mode in a.kondisi:
        path = out / f"{mode}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for i, qid in enumerate(ids, 1):
                q = qs[qid]
                t = time.perf_counter()
                d = rec = err = None
                try:
                    d, rec = run_condition(mode, q["question_text"], config=cfg, tau=tau, session_id=run_id)
                except Exception as exc:                       # tanpa Decision: dicatat, Q tidak dikurangi (D10 C7)
                    err = f"{type(exc).__name__}: {str(exc)[:200]}"
                ms = round((time.perf_counter() - t) * 1000, 1)
                f.write(json.dumps(record_from(qid, q["domain"], mode, d, rec, ms, err), ensure_ascii=False) + "\n")
                f.flush()
                print(f"[{mode} {i}/{len(ids)}] {qid} -> {d.decision + (' ' + d.reason_code if d.reason_code else '') if d else 'ERROR ' + err}  {ms:.0f} ms")
    manifest["finished_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Selesai: {out}")
    return 0


def _read_records(run_dir: Path, mode: str) -> list[dict]:
    path = run_dir / f"{mode}.jsonl"
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def replay_k3(rec: dict, tau: dict, catalog) -> dict:
    """Ulang keputusan S7 dari suara tersimpan dengan tau lain (tanpa model/DB). Keputusan sebelum S6 tidak berubah."""
    from backend.app.schemas import VoteResult
    from backend.app.steps.s7_decide import decide
    log = rec.get("log") or {}
    votes = [VoteResult.model_validate(v) for v in log.get("votes") or []]
    if not votes or rec.get("decision") is None:
        return rec
    cands = {c: catalog.candidate(c) for c in (log.get("k_prime") or []) if c in catalog.indicators}
    d = decide(votes, tau, candidates=cands, period_used=rec.get("period_used"))
    out = dict(rec)
    out.update(decision=d.decision, reason_code=d.reason_code,
               answer_rows=d.answer.result.rows if d.answer else None,
               answer_columns=d.answer.result.columns if d.answer else None,
               answer_error=d.answer.result.error if d.answer else None)
    return out


def cmd_calibrate(a) -> int:
    from backend.app.catalog import get_catalog
    cfg = load_config()
    manifest = json.loads((a.run / "manifest.json").read_text(encoding="utf-8"))
    if manifest["split"] != "dev":
        raise SystemExit("Kalibrasi hanya boleh memakai run dev (D10 CAL-05)")
    ids = set(manifest["question_ids"])
    labels = load_labels(a.label_final, a.pertanyaan, ids)
    records = _read_records(a.run, "K3")
    if {r["question_id"] for r in records} != ids:
        raise SystemExit("Kalibrasi memerlukan seluruh ID run dev, termasuk catatan kegagalan.")
    grid = cfg["evaluation"]["tau_grid"]
    units = sorted(grid)
    cat = get_catalog()
    results = []
    for combo in itertools.product(*(grid[u] for u in units)):
        tau = dict(zip(units, map(float, combo)))
        m = em.compute([replay_k3(r, tau, cat) for r in records], labels)
        f1 = m["F1_TANYA"]["value"]
        results.append({"tau": tau, "F1_TANYA": f1, "TKS": m["TKS"]["value"], "PBT": m["PBT"]["value"],
                        "EX": m["EX"]["value"]})
    # tujuan (config evaluation.tau_objective): F1 TANYA maksimum, lalu TKS minimum, lalu tau terkecil
    results.sort(key=lambda r: (-(r["F1_TANYA"] if r["F1_TANYA"] is not None else -1.0),
                                r["TKS"] if r["TKS"] is not None else 1.0, tuple(r["tau"][u] for u in units)))
    best = results[0]
    report = {"run": manifest["run_id"], "objective": cfg["evaluation"]["tau_objective"], "grid": grid,
              "n_dev": len(labels), "best": best, "top10": results[:10], "all_candidates": results,
              "computed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (a.run / "kalibrasi_tau.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for r in results[:10]:
        print(f"tau={r['tau']}  F1={r['F1_TANYA']}  TKS={r['TKS']}  PBT={r['PBT']}  EX={r['EX']}")
    print(f"TERPILIH: {best['tau']}")
    if a.tulis:
        path = ROOT / cfg["decision"]["tau_u_file"]
        lines = [f"# Dikalibrasi pada dev ({manifest['run_id']}, {len(labels)} pertanyaan), "
                 f"tujuan {cfg['evaluation']['tau_objective']}.",
                 "# KANDIDAT hasil dev; memerlukan review/pembekuan manusia sebelum test (D10 CAL-05)."]
        lines += [f'"{u}": {best["tau"][u]}' for u in units]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Ditulis: {path}")
    return 0


def cmd_metrics(a) -> int:
    manifest = json.loads((a.run / "manifest.json").read_text(encoding="utf-8"))
    if not manifest.get("question_ids"):
        raise SystemExit("Manifest belum menyimpan question_ids; penyebut tidak boleh ditebak dari hasil yang tersisa.")
    labels = load_labels(a.label_final, a.pertanyaan, set(manifest["question_ids"]))
    summary = defaultdict(dict)
    for mode in manifest["conditions"]:
        records = _read_records(a.run, mode)
        unlabeled = sorted({r["question_id"] for r in records} - set(labels))
        if unlabeled:
            raise SystemExit(f"{mode}: {len(unlabeled)} pertanyaan run belum berlabel final, Q tidak boleh dikurangi: "
                             f"{unlabeled[:10]}")
        sub = {q: labels[q] for q in manifest["question_ids"]}
        res = em.compute_breakdown(records, sub)
        res["run"] = manifest["run_id"]
        res["split"] = manifest["split"]
        (a.run / f"metrik_{mode}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        s = res["semua"]
        summary[mode] = {k: (s[k]["num"], s[k]["den"], s[k]["value"]) for k in
                         ("TKS", "PBT", "F1_TANYA", "EX", "linking_any")}
        summary[mode]["p50_ms"] = s["latency_ms"]["p50"]
        summary[mode]["p95_ms"] = s["latency_ms"]["p95"]
    for mode, s in summary.items():
        print(mode, json.dumps(s, ensure_ascii=False))
    print(f"Rincian per kelompok/domain: {a.run}/metrik_<kondisi>.json")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--kondisi", nargs="+", choices=["K1", "K2", "K3"], required=True)
    p.add_argument("--split", choices=["dev", "test"], required=True)
    p.add_argument("--split-file", type=Path, required=True)
    p.add_argument("--pertanyaan", type=Path, default=ANN / "pertanyaan.csv")
    p.add_argument("--label-final", type=Path, default=ANN / "label_final.csv")
    p.add_argument("--tau-nol", action="store_true", help="tau 0 sementara; hanya run dev untuk kalibrasi replay")
    p.add_argument("--check-only", action="store_true", help="periksa prasyarat tanpa model atau membuat run")
    p.add_argument("--nama")
    for name in ("kalibrasi", "metrik"):
        p = sub.add_parser(name)
        p.add_argument("run", type=Path)
        p.add_argument("--label-final", type=Path, default=ANN / "label_final.csv")
        p.add_argument("--pertanyaan", type=Path, default=ANN / "pertanyaan.csv")
        if name == "kalibrasi":
            p.add_argument("--tulis", action="store_true", help="tulis tau terpilih ke config/tau_u.yaml")
    a = ap.parse_args(argv)
    return {"run": cmd_run, "kalibrasi": cmd_calibrate, "metrik": cmd_metrics}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
