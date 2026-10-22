"""Probe M3: ukur tingkat SQL valid dan keputusan pipeline K3 dengan model NYATA (penyaji model profil aktif harus berjalan).

  python scripts/probe_m3.py                 # pertanyaan probe bawaan
  python scripts/probe_m3.py "Pertanyaan 1" "Pertanyaan 2"

Pertanyaan bawaan adalah PROBE ad hoc, BUKAN himpunan uji/dev: jangan dipakai lagi sebagai soal evaluasi.
Hasil disimpan ke eval/runs/probe/<waktu>_v<prompt>.json (seluruh SQL hasil parse, alasan tolak, latensi, keputusan).
tau dibaca dari config; bila belum dikalibrasi, keputusan yang butuh tau dicatat sebagai galat konfigurasi, bukan dipaksa.
"""
import collections
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import ConfigError, load_config  # noqa: E402
from backend.app.orchestrator import run_question_with_log  # noqa: E402

PROBE = [
    "Provinsi mana dengan persentase penduduk miskin tertinggi?",
    "Berapa persentase penduduk miskin di Aceh?",
    "Provinsi mana dengan tingkat pengangguran terbuka terendah?",
    "Berapa jumlah penduduk miskin di Jawa Timur?",
    "Rata-rata tingkat pengangguran terbuka di pulau jawa?",
    "Provinsi mana dengan APM SMA paling rendah?",
]


def main() -> int:
    cfg = load_config()
    questions = sys.argv[1:] or PROBE
    rows, total, valid = [], 0, 0
    for q in questions:
        try:
            d, rec = run_question_with_log(q, config=cfg, session_id="probe")
            dec = f"{d.decision} {d.reason_code or ''}".strip()
        except ConfigError as exc:                       # mis. tau_u belum dikalibrasi
            rows.append({"question": q, "decision": f"CONFIG_ERROR: {exc}"})
            print(f"\n[{q}]\n  CONFIG_ERROR: {exc}")
            continue
        sk = rec.skeletons
        n_valid = sum(s.valid for s in sk)
        total += len(sk)
        valid += n_valid
        reasons = collections.Counter(s.reject_reason for s in sk if not s.valid).most_common(5)
        top_sql = collections.Counter(s.sql for s in sk if s.valid).most_common(1)
        winner_err = next((v.result.error for v in rec.votes if v.result.error), None)
        rows.append({"question": q, "k": rec.k, "k_prime": rec.k_prime, "decision": dec,
                     "samples": len(sk), "valid": n_valid, "reject_reasons": reasons,
                     "winner_error": winner_err, "latency_ms": rec.latency_ms,
                     "extraction": rec.extraction.model_dump() if rec.extraction else None,
                     "winners": [v.model_dump() for v in rec.votes],
                     "skeletons": [s.model_dump() for s in sk]})
        print(f"\n[{q}]\n  K={rec.k} K'={rec.k_prime} -> {dec}")
        if sk:
            print(f"  valid {n_valid}/{len(sk)}  s4={rec.latency_ms.get('s4', 0):.0f} ms")
            for r, n in reasons:
                print(f"    {n:2d}x {r}")
            if top_sql:
                print(f"  SQL valid terbanyak ({top_sql[0][1]}x):\n    " + top_sql[0][0].replace("\n", "\n    "))
            if winner_err:
                print(f"  galat pemenang: {winner_err}")
            for v in rec.votes:
                print(f"  pemenang {v.candidate_code}: {v.votes} suara{' (seri)' if v.tie else ''}, "
                      f"kolom={v.result.columns} baris={v.result.rows[:5]}{' ...' if len(v.result.rows) > 5 else ''}")
    rate = f"{valid}/{total} ({100 * valid / total:.1f}%)" if total else "tidak ada pemanggilan model"
    print(f"\nRINGKASAN prompt v{cfg['prompt']['version']}: SQL valid {rate}")
    out = ROOT / "eval" / "runs" / "probe" / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex}_v{cfg['prompt']['version']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps({"prompt_version": str(cfg["prompt"]["version"]), "model": cfg["model"]["name"],
                               "probe_not_test_set": True, "valid": valid, "samples": total, "results": rows},
                              ensure_ascii=False, indent=2) + "\n")
    print(f"Disimpan: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
