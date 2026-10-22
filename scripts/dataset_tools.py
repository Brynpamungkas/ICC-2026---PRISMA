"""Alat dataset evaluasi (D10 C3-C4, D11 D3/D8). Tidak membuat label: hanya memeriksa, mengeksekusi kueri rujukan
yang DITULIS MANUSIA, menghitung kappa, dan membagi dev/test secara deterministik.

  python scripts/dataset_tools.py katalog                          # lembar bantu penulis pertanyaan
  python scripts/dataset_tools.py cek-pertanyaan eval/annotations/pertanyaan.csv
  python scripts/dataset_tools.py buat-sql eval/annotations/label_A.csv  # SQL rujukan dari isian terstruktur
  python scripts/dataset_tools.py cek-label eval/annotations/label_A.csv --pertanyaan eval/annotations/pertanyaan.csv
  python scripts/dataset_tools.py laporan-koreksi eval/annotations/label_draf_llm.csv eval/annotations/label_final.csv
  python scripts/dataset_tools.py kappa eval/annotations/label_A.csv eval/annotations/label_B.csv
  python scripts/dataset_tools.py split eval/annotations/pertanyaan.csv eval/annotations/label_final.csv --seed <seed>

Format kolom: lihat eval/annotations/templates/README.md.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DOMAINS = ["kemiskinan", "ketenagakerjaan", "pendidikan"]
GROUPS = ["TAK_AMBIGU", "AMBIGU_TEKS", "AMBIGU_ANGKA_SAMA", "AMBIGU_ANGKA_BEDA"]     # urutan Tabel VIII = tie-break
DECISIONS = {"JAWAB", "TANYA"}                                                     # TAHAN bukan label utama (D11 D4)
SOURCES = {"mahasiswa", "tim", "llm"}                                              # llm: keputusan tim 20 Okt 2026, wajib diungkap di paper
STATUSES = {"DRAFT", "NEEDS_REVIEW", "VERIFIED"}
_OP = re.compile(r"^(NONE|SUM|AVG|RANK_(DESC|ASC)_([1-9]\d*))$")             # RANK_DESC_1 = tertinggi, RANK_ASC_3 = 3 terendah
DOMAIN_OF = {"KMS_": "kemiskinan", "TPT_": "ketenagakerjaan", "PGR_": "ketenagakerjaan",
             "APK_": "pendidikan", "APM_": "pendidikan", "APS_": "pendidikan"}
# Paper Tabel VIII (D10 EVAL-05): fakta paper, bukan parameter penyetelan.
COMPOSITION = {
    ("TAK_AMBIGU", "kemiskinan"): 20, ("TAK_AMBIGU", "ketenagakerjaan"): 20, ("TAK_AMBIGU", "pendidikan"): 15,
    ("AMBIGU_TEKS", "kemiskinan"): 20, ("AMBIGU_TEKS", "ketenagakerjaan"): 20, ("AMBIGU_TEKS", "pendidikan"): 15,
    ("AMBIGU_ANGKA_SAMA", "kemiskinan"): 0, ("AMBIGU_ANGKA_SAMA", "ketenagakerjaan"): 0, ("AMBIGU_ANGKA_SAMA", "pendidikan"): 30,
    ("AMBIGU_ANGKA_BEDA", "kemiskinan"): 20, ("AMBIGU_ANGKA_BEDA", "ketenagakerjaan"): 20, ("AMBIGU_ANGKA_BEDA", "pendidikan"): 0,
}
MAHASISWA_TARGET = 60                                                              # D10 EVAL-06
# Pertanyaan probe M3 (scripts/probe_m3.py) sudah dipakai untuk menyetel prompt: dilarang masuk corpus.
PROBE_EXCLUDED = [
    "Provinsi mana dengan persentase penduduk miskin tertinggi?",
    "Berapa persentase penduduk miskin di Aceh?",
    "Provinsi mana dengan tingkat pengangguran terbuka terendah?",
    "Berapa jumlah penduduk miskin di Jawa Timur?",
    "Rata-rata tingkat pengangguran terbuka di pulau jawa?",
    "Provinsi mana dengan APM SMA paling rendah?",
]
Q_COLS = ["question_id", "domain", "target_group", "source_kind", "source_record_id", "author", "question_text"]
L_COLS = ["question_id", "annotator_id", "question_group", "decision_reference", "interpretation_id", "meaning",
          "indicator_code", "region_codes", "period", "operation", "reference_sql", "rationale", "uncertainty_notes",
          "source_refs", "verification_status"]


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.casefold())).strip()


def read_csv(path: Path, cols: list[str]) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        missing = [c for c in cols if c not in (reader.fieldnames or [])]
    if missing:
        raise SystemExit(f"{path.name}: kolom hilang {missing}")
    return [{k: (v or "").strip() for k, v in r.items() if k} for r in rows]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------- komposisi ----------
def check_questions(rows: list[dict]) -> tuple[list[str], dict]:
    errs: list[str] = []
    ids = Counter(r["question_id"] for r in rows)
    errs += [f"question_id ganda: {i}" for i, n in ids.items() if n > 1 or not i]
    probe = {norm(q) for q in PROBE_EXCLUDED}
    seen: dict[str, str] = {}
    for r in rows:
        qid = r["question_id"]
        if r["domain"] not in DOMAINS:
            errs.append(f"{qid}: domain tidak dikenal {r['domain']!r}")
        if r["target_group"] not in GROUPS:
            errs.append(f"{qid}: target_group tidak dikenal {r['target_group']!r}")
        if r["source_kind"] not in SOURCES:
            errs.append(f"{qid}: source_kind harus mahasiswa/tim/llm")
        if not r["question_text"]:
            errs.append(f"{qid}: question_text kosong")
        n = norm(r["question_text"])
        if n in probe:
            errs.append(f"{qid}: pertanyaan probe M3 dilarang masuk corpus")
        if n and n in seen:
            errs.append(f"{qid}: teks sama dengan {seen[n]}")
        seen.setdefault(n, qid)
    counts = Counter((r["target_group"], r["domain"]) for r in rows)
    stats = {"cells": {f"{g}|{d}": [counts.get((g, d), 0), COMPOSITION[(g, d)]] for g in GROUPS for d in DOMAINS},
             "total": [len(rows), sum(COMPOSITION.values())],
             "mahasiswa": [sum(r["source_kind"] == "mahasiswa" for r in rows), MAHASISWA_TARGET]}
    return errs, stats


def composition_complete(stats: dict) -> bool:
    """Sel Tabel VIII harus tepat. Jumlah sumber mahasiswa dilaporkan terpisah (penyimpangan dicatat D13, bukan galat)."""
    return all(a == b for a, b in stats["cells"].values())


def print_matrix(stats: dict) -> None:
    print(f"{'kelompok':<20}" + "".join(f"{d:>18}" for d in DOMAINS))
    for g in GROUPS:
        cells = [stats["cells"][f"{g}|{d}"] for d in DOMAINS]
        print(f"{g:<20}" + "".join(f"{f'{a}/{b}':>18}" for a, b in cells))
    print(f"total {stats['total'][0]}/{stats['total'][1]}   mahasiswa {stats['mahasiswa'][0]}/{stats['mahasiswa'][1]}")


# ---------- label ----------
def group_labels(rows: list[dict]) -> dict[str, list[dict]]:
    by_q: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_q[r["question_id"]].append(r)
    return by_q


def check_labels(rows: list[dict], question_ids: set[str] | None, indicator_codes: set[str]) -> list[str]:
    errs: list[str] = []
    by_q = group_labels(rows)
    annotators = {r["annotator_id"] for r in rows}
    if len(annotators) != 1:
        errs.append(f"satu berkas label harus satu penilai, ditemukan {sorted(annotators)}")
    for qid, items in by_q.items():
        if question_ids is not None and qid not in question_ids:
            errs.append(f"{qid}: tidak ada di berkas pertanyaan")
        for col in ("decision_reference", "question_group"):
            vals = {r[col] for r in items}
            if len(vals) != 1:
                errs.append(f"{qid}: {col} berbeda antarbaris {sorted(vals)}")
        dec, grp = items[0]["decision_reference"], items[0]["question_group"]
        if dec not in DECISIONS:
            errs.append(f"{qid}: decision_reference harus JAWAB/TANYA (TAHAN bukan label utama)")
        if grp not in GROUPS:
            errs.append(f"{qid}: question_group tidak dikenal {grp!r}")
        ids = [r["interpretation_id"] for r in items]
        if len(set(ids)) != len(ids) or "" in ids:
            errs.append(f"{qid}: interpretation_id kosong/ganda")
        if dec == "TANYA" and len(items) < 2:
            errs.append(f"{qid}: TANYA butuh minimal dua interpretasi sah (RUB-06)")
        for r in items:
            if r["indicator_code"] not in indicator_codes:
                errs.append(f"{qid}/{r['interpretation_id']}: indicator_code {r['indicator_code']!r} tidak ada di katalog")
            if not r["reference_sql"]:
                errs.append(f"{qid}/{r['interpretation_id']}: reference_sql kosong")
            if not _OP.match(r["operation"]):
                errs.append(f"{qid}/{r['interpretation_id']}: operation harus NONE/SUM/AVG/RANK_DESC_k/RANK_ASC_k")
            if r["verification_status"] not in STATUSES:
                errs.append(f"{qid}/{r['interpretation_id']}: verification_status harus DRAFT/NEEDS_REVIEW/VERIFIED")
    if question_ids is not None:
        errs += [f"{q}: belum dilabel" for q in sorted(question_ids - set(by_q))]
    return errs


def execute_reference(rows: list[dict], db_path: Path | None) -> list[dict]:
    from backend.app.sqlguard.executor import run_query
    out = []
    for r in rows:
        sql = r["reference_sql"]
        if not re.match(r"^\s*(select|with)\b", sql, re.I):
            res = {"columns": [], "rows": [], "error": "BUKAN_SELECT"}
        else:
            raw = run_query(sql, {}, db_path=db_path)
            res = {"columns": raw.columns, "rows": raw.rows, "error": raw.error}
        body = json.dumps([res["columns"], res["rows"], res["error"]], ensure_ascii=False, sort_keys=True)
        out.append({"question_id": r["question_id"], "annotator_id": r["annotator_id"],
                    "interpretation_id": r["interpretation_id"], "indicator_code": r["indicator_code"],
                    "reference_sql": sql, **res, "execution_status": "OK" if res["error"] is None else res["error"],
                    "content_status": "NO_ROWS" if res["error"] is None and not res["rows"] else None,
                    "result_hash": hashlib.sha256(body.encode()).hexdigest()})
    return out


# ---------- kappa (D11 ANN-10) ----------
def cohen_kappa(a: dict[str, str], b: dict[str, str], categories=("JAWAB", "TANYA")) -> dict:
    ids = sorted(set(a) & set(b))
    pairs = [(a[i], b[i]) for i in ids if a[i] in categories and b[i] in categories]
    n = len(pairs)
    table = {x: {y: sum(1 for p in pairs if p == (x, y)) for y in categories} for x in categories}
    rep = {"N": n, "only_A": sorted(set(a) - set(b)), "only_B": sorted(set(b) - set(a)),
           "invalid": sorted(i for i in ids if a[i] not in categories or b[i] not in categories),
           "contingency_A_rows_B_cols": table}
    if n == 0:
        return {**rep, "Po": None, "Pe": None, "kappa": None, "note": "N/A: tidak ada pasangan lengkap"}
    po = sum(table[c][c] for c in categories) / n
    pe = sum((sum(table[c].values()) / n) * (sum(table[x][c] for x in categories) / n) for c in categories)
    if math.isclose(pe, 1.0):
        return {**rep, "Po": po, "Pe": pe, "kappa": None, "note": "N/A: Pe=1 (penyebut nol)"}
    return {**rep, "Po": po, "Pe": pe, "kappa": (po - pe) / (1 - pe)}


# ---------- split (D10 EVAL-07) ----------
def hamilton_quotas(cell_sizes: dict[tuple[str, str], int], fraction: float) -> dict[tuple[str, str], int]:
    total = sum(cell_sizes.values())
    target = round(fraction * total)
    order = [(g, d) for g in GROUPS for d in DOMAINS]
    exact = {k: fraction * cell_sizes.get(k, 0) for k in order}
    quota = {k: math.floor(v + 1e-9) for k, v in exact.items()}
    rest = target - sum(quota.values())
    ranked = sorted(order, key=lambda k: (-(exact[k] - quota[k]), order.index(k)))
    for k in ranked[:rest]:
        quota[k] += 1
    return quota


def split_ids(cells: dict[tuple[str, str], list[str]], quotas: dict[tuple[str, str], int], seed: str) -> tuple[list[str], list[str]]:
    dev, test = [], []
    for key in [(g, d) for g in GROUPS for d in DOMAINS]:
        ids = sorted(cells.get(key, []), key=lambda i: (hashlib.sha256(f"{seed}\x1f{i}".encode()).hexdigest(), i))
        dev += ids[:quotas.get(key, 0)]
        test += ids[quotas.get(key, 0):]
    return sorted(dev), sorted(test)


# ---------- bantu penilai: SQL rujukan dari isian terstruktur ----------
def _quote(v: str) -> str:
    return "'" + v.replace("'", "''") + "'"


def build_reference_sql(indicator: str, period: str, regions: list[str], operation: str) -> str:
    """SQL rujukan deterministik dari pilihan penilai (bukan tebakan AI). Penilai tetap memverifikasi hasilnya."""
    where = [f"n.kode_indikator = {_quote(indicator)}", f"n.periode = {_quote(period)}"]
    if regions:
        where.append("n.kode_provinsi IN (" + ", ".join(_quote(r) for r in regions) + ")")
    cond = " AND ".join(where)
    m = _OP.match(operation)
    if not m:
        raise ValueError(f"operation tidak dikenal: {operation}")
    if m.group(1) in ("SUM", "AVG"):
        return f"SELECT {m.group(1)}(n.nilai) AS nilai FROM nilai_indikator n WHERE {cond}"
    base = ("SELECT p.nama AS wilayah, n.nilai AS nilai FROM nilai_indikator n "
            f"JOIN provinsi p ON p.kode = n.kode_provinsi WHERE {cond}")
    if m.group(2):
        return f"{base} ORDER BY n.nilai {m.group(2)}, p.nama LIMIT {m.group(3)}"
    return f"{base} ORDER BY p.nama"


def fill_reference_sql(rows: list[dict], cat) -> tuple[list[dict], list[str]]:
    """Isi reference_sql yang KOSONG. Periode kosong = periode terbaru yang tersedia bagi SEMUA interpretasi pertanyaan
    itu (aturan paper III-C) dan ditandai di uncertainty_notes agar diverifikasi manusia."""
    notes: list[str] = []
    out = [dict(r) for r in rows]
    for qid, items in group_labels(out).items():
        common = None
        for r in items:
            per = set(cat.indicators[r["indicator_code"]].periods) if r["indicator_code"] in cat.indicators else set()
            common = per if common is None else common & per
        for r in items:
            if r["reference_sql"]:
                continue
            code = r["indicator_code"]
            if code not in cat.indicators:
                notes.append(f"{qid}/{r['interpretation_id']}: indicator_code {code!r} tidak dikenal")
                continue
            meta = cat.indicators[code]
            if not r["period"]:
                if not common:
                    notes.append(f"{qid}: tidak ada periode yang tersedia bagi semua interpretasi; isi period manual")
                    continue
                r["period"] = max(common)
                r["uncertainty_notes"] = (r["uncertainty_notes"] + "; " if r["uncertainty_notes"] else "") + \
                    "periode diisi otomatis: terbaru bersama (verifikasi)"
            if r["period"] not in meta.periods:
                notes.append(f"{qid}/{r['interpretation_id']}: periode {r['period']} tidak tersedia untuk {code} "
                             f"(tersedia {sorted(meta.periods)})")
                continue
            regions = [x.strip() for x in r["region_codes"].split(";") if x.strip()]
            bad = [x for x in regions if x not in cat.provinces or x not in meta.regions]
            if bad:
                notes.append(f"{qid}/{r['interpretation_id']}: kode provinsi tidak dikenal/tidak tercakup {bad}")
                continue
            if r["operation"] == "SUM" and meta.unit == "%":
                notes.append(f"{qid}/{r['interpretation_id']}: SUM atas persen tidak sah (paper A-4); interpretasi ini "
                             "seharusnya ditolak, bukan diberi SQL")
                continue
            try:
                r["reference_sql"] = build_reference_sql(code, r["period"], regions, r["operation"])
            except ValueError as exc:
                notes.append(f"{qid}/{r['interpretation_id']}: {exc}")
    return out, notes


def catalog_sheet(cat) -> str:
    """Lembar bantu penulis pertanyaan: indikator, satuan, periode, istilah ambigu dan kode provinsi (fakta katalog)."""
    lines = ["INDIKATOR (kode | nama | satuan | periode tersedia)"]
    for code, m in cat.indicators.items():
        dom = next((d for p, d in DOMAIN_OF.items() if code.startswith(p)), "?")
        lines.append(f"  [{dom}] {code} | {m.name} | {m.unit} | {', '.join(sorted(m.periods))}")
    lines.append("\nISTILAH KAMUS YANG MENUNJUK >1 INDIKATOR (sumber ambiguitas)")
    for term, kinds in sorted(cat.kamus.items()):
        codes = [c for c in cat.indicators if c in kinds.get("indikator", set())]
        if len(codes) > 1:
            units = {cat.indicators[c].unit for c in codes}
            hint = "angka satuan SAMA" if len(units) == 1 else "angka satuan BEDA"
            lines.append(f"  '{' '.join(term)}' -> {', '.join(codes)}  [{hint}; peringkat -> kolom teks]")
    lines.append("\nWILAYAH (kode | nama) dan alias kamus")
    for code, name in sorted(cat.provinces.items()):
        lines.append(f"  {code} | {name}")
    for term, kinds in sorted(cat.kamus.items()):
        regs = kinds.get("wilayah", set())
        if len(regs) > 1:
            lines.append(f"  alias '{' '.join(term)}' -> {', '.join(sorted(regs))}")
    return "\n".join(lines)


def write_csv(path: Path, rows: list[dict], cols: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


# ---------- supplementary draft-correction report; not a replacement for D11 kappa ----------
def _signature(items: list[dict]) -> dict:
    return {"decision": items[0]["decision_reference"], "group": items[0]["question_group"],
            "interps": sorted((r["indicator_code"], ";".join(sorted(x for x in r["region_codes"].split(";") if x)),
                               r["period"], r["operation"]) for r in items)}


def correction_report(draft: list[dict], final: list[dict]) -> dict:
    d, f = group_labels(draft), group_labels(final)
    qids = sorted(set(d) & set(f))
    verified = [q for q in qids if all(r["verification_status"] == "VERIFIED" for r in f[q])]
    changed = {k: [] for k in ("decision", "group", "interps")}
    for q in verified:
        a, b = _signature(d[q]), _signature(f[q])
        for k in changed:
            if a[k] != b[k]:
                changed[k].append(q)
    any_change = sorted(set().union(*changed.values()))
    n = len(verified)
    return {"draft_questions": len(d), "verified_questions": n, "unverified": sorted(set(qids) - set(verified)),
            "changed_any": {"num": len(any_change), "den": n, "value": len(any_change) / n if n else None, "ids": any_change},
            **{f"changed_{k}": {"num": len(v), "den": n, "value": len(v) / n if n else None, "ids": v}
               for k, v in changed.items()}}


# ---------- CLI ----------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("cek-pertanyaan")
    p.add_argument("pertanyaan", type=Path)
    p = sub.add_parser("cek-label")
    p.add_argument("label", type=Path)
    p.add_argument("--pertanyaan", type=Path)
    p.add_argument("--db", type=Path)
    sub.add_parser("katalog")
    p = sub.add_parser("kerangka-label")
    p.add_argument("pertanyaan", type=Path)
    p.add_argument("--penilai", required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("buat-sql")
    p.add_argument("label", type=Path)
    p = sub.add_parser("laporan-koreksi")
    p.add_argument("draf", type=Path)
    p.add_argument("final", type=Path)
    p = sub.add_parser("kappa")
    p.add_argument("label_a", type=Path)
    p.add_argument("label_b", type=Path)
    p = sub.add_parser("split")
    p.add_argument("pertanyaan", type=Path)
    p.add_argument("label_final", type=Path, nargs="?",
                   help="opsional; tanpa ini sel strata memakai target_group penyusun (split sebelum pelabelan)")
    p.add_argument("--seed", required=True, help="disepakati tim sebelum split; dicatat di D13")
    p = sub.add_parser("cek-cakupan")
    p.add_argument("split_file", type=Path)
    p.add_argument("label_final", type=Path)
    p.add_argument("--bagian", choices=["dev", "test"], required=True)
    a = ap.parse_args(argv)

    if a.cmd == "cek-pertanyaan":
        errs, stats = check_questions(read_csv(a.pertanyaan, Q_COLS))
        print_matrix(stats)
        for e in errs:
            print("GALAT", e)
        done = not errs and composition_complete(stats)
        if stats["mahasiswa"][0] != stats["mahasiswa"][1]:
            print(f"CATATAN: sumber mahasiswa {stats['mahasiswa'][0]}/{stats['mahasiswa'][1]} -> penyimpangan dari paper, "
                  "wajib diungkap (D13 + Bab III/IV)")
        print("LENGKAP sesuai Tabel VIII" if done else "BELUM lengkap / ada galat")
        return 0 if done else 1

    if a.cmd == "katalog":
        from backend.app.catalog import get_catalog
        print(catalog_sheet(get_catalog()))
        return 0

    if a.cmd == "kerangka-label":
        if a.out.exists():
            raise SystemExit(f"{a.out} sudah ada; tidak ditimpa")
        qs = read_csv(a.pertanyaan, Q_COLS)
        cols = ["question_id", "question_text"] + [c for c in L_COLS if c != "question_id"]
        rows = [{"question_id": q["question_id"], "question_text": q["question_text"], "annotator_id": a.penilai,
                 "interpretation_id": "I1", "verification_status": "DRAFT"} for q in qs]
        write_csv(a.out, rows, cols)
        print(f"{len(rows)} baris -> {a.out}. Tambah baris I2, I3, ... untuk interpretasi sah lain.")
        return 0

    if a.cmd == "buat-sql":
        from backend.app.catalog import get_catalog
        rows = read_csv(a.label, L_COLS)
        filled, notes = fill_reference_sql(rows, get_catalog())
        backup = a.label.with_suffix(".sebelum-buat-sql.csv")
        backup.write_bytes(a.label.read_bytes())
        with open(a.label, encoding="utf-8-sig", newline="") as f:
            header = next(csv.reader(f))                                   # pertahankan kolom bantu (mis. question_text)
        write_csv(a.label, filled, header)
        n = sum(1 for x, y in zip(rows, filled) if x["reference_sql"] != y["reference_sql"])
        for msg in notes:
            print("PERLU DICEK", msg)
        print(f"{n} reference_sql diisi; salinan asli: {backup.name}. Verifikasi lalu jalankan cek-label.")
        return 0 if not notes else 1

    if a.cmd == "cek-label":
        from backend.app.catalog import get_catalog
        rows = read_csv(a.label, L_COLS)
        qids = {r["question_id"] for r in read_csv(a.pertanyaan, Q_COLS)} if a.pertanyaan else None
        errs = check_labels(rows, qids, set(get_catalog().indicators))
        answers = execute_reference(rows, a.db)
        out = a.label.with_suffix(".answers.jsonl")
        out.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in answers), encoding="utf-8")
        for x in answers:
            if x["error"] or x["content_status"]:
                errs.append(f"{x['question_id']}/{x['interpretation_id']}: kueri rujukan {x['error'] or x['content_status']}")
        for e in errs:
            print("GALAT", e)
        print(f"{len(group_labels(rows))} pertanyaan, {len(rows)} interpretasi; jawaban rujukan -> {out}")
        return 0 if not errs else 1

    if a.cmd == "laporan-koreksi":
        rep = correction_report(read_csv(a.draf, L_COLS), read_csv(a.final, L_COLS))
        rep["inputs"] = {a.draf.name: sha256_file(a.draf), a.final.name: sha256_file(a.final)}
        rep["computed_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0

    if a.cmd == "kappa":
        la, lb = read_csv(a.label_a, L_COLS), read_csv(a.label_b, L_COLS)
        da = {q: items[0]["decision_reference"] for q, items in group_labels(la).items()}
        db = {q: items[0]["decision_reference"] for q, items in group_labels(lb).items()}
        rep = cohen_kappa(da, db)
        ga = {q: items[0]["question_group"] for q, items in group_labels(la).items()}
        gb = {q: items[0]["question_group"] for q, items in group_labels(lb).items()}
        common = sorted(set(ga) & set(gb))
        rep["question_group_raw_agreement"] = (sum(ga[q] == gb[q] for q in common) / len(common)) if common else None
        rep["disagree_decision"] = sorted(q for q in set(da) & set(db) if da[q] != db[q])
        rep["inputs"] = {a.label_a.name: sha256_file(a.label_a), a.label_b.name: sha256_file(a.label_b)}
        rep["computed_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0

    if a.cmd == "cek-cakupan":
        ids = json.loads(a.split_file.read_text(encoding="utf-8"))[a.bagian]
        groups = group_labels(read_csv(a.label_final, L_COLS))
        labeled = {q for q, items in groups.items() if all(r["verification_status"] == "VERIFIED" for r in items)}
        missing = [i for i in ids if i not in labeled]
        print(f"{a.bagian}: {len(ids) - len(missing)}/{len(ids)} berlabel final dan VERIFIED")
        if missing:
            print("BELUM berlabel:", ", ".join(missing[:20]), "..." if len(missing) > 20 else "")
        return 0 if not missing else 1

    if a.cmd == "split":
        from backend.app.config import load_config
        qs = read_csv(a.pertanyaan, Q_COLS)
        cells: dict[tuple[str, str], list[str]] = defaultdict(list)
        if a.label_final:
            final = group_labels(read_csv(a.label_final, L_COLS))
            missing = sorted({r["question_id"] for r in qs} - set(final))
            if missing:
                print("GALAT belum ada label final:", missing[:10], "..." if len(missing) > 10 else "")
                return 1
            for r in qs:
                cells[(final[r["question_id"]][0]["question_group"], r["domain"])].append(r["question_id"])
        else:                       # keputusan tim 21 Okt: strata = target_group, split dibuat sebelum label dibuka
            for r in qs:
                cells[(r["target_group"], r["domain"])].append(r["question_id"])
        sizes = {k: len(v) for k, v in cells.items()}
        if any(sizes.get(k, 0) != n for k, n in COMPOSITION.items()):
            print("PERINGATAN komposisi label final tidak sama dengan Tabel VIII; laporkan sebagai penyimpangan.")
        frac = float(load_config()["evaluation"]["dev_fraction"])
        quotas = hamilton_quotas(sizes, frac)
        dev, test = split_ids(cells, quotas, a.seed)
        manifest = {"seed": a.seed, "dev_fraction": frac, "method": "Hamilton per sel kelompok x domain; "
                    "urut SHA256(seed + U+001F + question_id)", "quotas": {f"{g}|{d}": q for (g, d), q in quotas.items()},
                    "strata": "question_group label_final" if a.label_final else "target_group penyusun",
                    "dev": dev, "test": test, "inputs": {a.pertanyaan.name: sha256_file(a.pertanyaan)}
                    | ({a.label_final.name: sha256_file(a.label_final)} if a.label_final else {}),
                    "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        out = ROOT / "eval" / "testset" / f"split_seed-{re.sub(r'[^A-Za-z0-9_-]', '_', a.seed)}.json"
        out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"dev {len(dev)} / test {len(test)} -> {out}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
