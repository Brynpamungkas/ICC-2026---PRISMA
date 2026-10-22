"""Langkah 1: normalisasi dan ekstraksi (K-12). Kontrak: ExtractionResult. Deterministik, tanpa model.

Aturan (PAPER III-B/III-C kecuali ditandai PROPOSED):
- exact match setelah normalisasi pada kamus; tanpa fuzzy/embedding/stemming.
- PROPOSED K-12 (config extraction.suppress_covered_terms): istilah yang seluruhnya berada di dalam istilah
  lebih panjang tidak dihitung, agar "apm sma" tidak ikut menarik semua kandidat "apm".
- PROPOSED K-02: kata operasi ("jumlah") yang menjadi bagian istilah indikator ("jumlah penduduk miskin")
  tidak dihitung sebagai SUM.
- PROPOSED: wilayah/bulan yang disebut tetapi tidak dikenal dicatat di `unresolved` (-> T2). Tanpa ini sistem akan
  menjawab "semua provinsi" secara diam-diam: kegagalan senyap.
- PROPOSED K-12 (config extraction.strip_enclitic_nya, 21 Okt): token berakhiran "-nya" diganti bentuk dasarnya HANYA bila
  bentuk dasar itu adalah token kamus ("kemiskinannya" -> "kemiskinan"). Bukan stemming: tidak ada imbuhan lain yang dibuang.
- PROPOSED (21 Okt): kata peringkat boleh tumpang tindih dengan istilah indikator ("termiskin" = istilah + arah), tetapi
  tidak dengan wilayah/periode.
"""
from __future__ import annotations

import re

from backend.app.catalog import Catalog, get_catalog
from backend.app.config import load_config
from backend.app.schemas import ExtractionResult
from backend.app.text import tokenize

MONTHS = {"januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6, "juli": 7,
          "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12}
_YEAR = re.compile(r"^(19|20)\d\d$")


def _find_spans(tokens: list[str], phrase: tuple[str, ...]) -> list[tuple[int, int]]:
    n = len(phrase)
    return [(i, i + n) for i in range(len(tokens) - n + 1) if tuple(tokens[i:i + n]) == phrase]


def _suppress(matches: list[dict]) -> list[dict]:
    kept = []
    for m in matches:
        covered = any(o is not m and o["jenis"] == m["jenis"] and o["span"][0] <= m["span"][0]
                      and m["span"][1] <= o["span"][1] and o["span"] != m["span"] for o in matches)
        if not covered:
            kept.append(m)
    return kept


def _extract_period(tokens: list[str]) -> tuple[str | None, list[str], set[int]]:
    """Return (period, unresolved, consumed token indexes). YYYY-MM only when month is explicit (K-18: never invent months)."""
    consumed: set[int] = set()
    unresolved: list[str] = []
    period = None
    for i, t in enumerate(tokens):
        if _YEAR.match(t):
            if i + 1 < len(tokens) and re.fullmatch(r"(0[1-9]|1[0-2])", tokens[i + 1]):      # "2025-09"
                period = f"{t}-{tokens[i + 1]}"
                consumed |= {i, i + 1}
            elif i > 0 and tokens[i - 1] in MONTHS:                                         # "september 2025"
                period = f"{t}-{MONTHS[tokens[i - 1]]:02d}"
                consumed |= {i - 1, i}
            else:                                                                           # bare year: no month invented
                period = t
                consumed.add(i)
        elif t in MONTHS and not (i + 1 < len(tokens) and _YEAR.match(tokens[i + 1])):
            unresolved.append(f"bulan {t} tanpa tahun")
            consumed.add(i)
    return period, unresolved, consumed


def _strip_enclitic(tokens: list[str], cat: Catalog) -> list[str]:
    vocab = {w for phrase in cat.kamus for w in phrase}
    return [t[:-3] if t.endswith("nya") and t not in vocab and t[:-3] in vocab else t for t in tokens]


def extract(question: str, *, catalog: Catalog | None = None, config: dict | None = None) -> ExtractionResult:
    cat = catalog or get_catalog()
    cfg = (config or load_config())["extraction"]
    tokens = tokenize(question)
    if cfg.get("strip_enclitic_nya"):
        tokens = _strip_enclitic(tokens, cat)

    matches = []
    for phrase, by_jenis in cat.kamus.items():
        for span in _find_spans(tokens, phrase):
            for jenis in by_jenis:
                matches.append({"span": span, "phrase": phrase, "jenis": jenis})
    if cfg["suppress_covered_terms"]:
        matches = _suppress(matches)
    matches.sort(key=lambda m: (m["span"][0], -m["span"][1]))

    terms: list[str] = []
    regions: list[str] = []
    consumed: set[int] = set()
    non_term: set[int] = set()                      # token wilayah/periode: tidak boleh dipakai kata peringkat
    for m in matches:
        consumed |= set(range(*m["span"]))
        if m["jenis"] != "indikator":
            non_term |= set(range(*m["span"]))
        if m["jenis"] == "indikator":
            term = " ".join(m["phrase"])
            if term not in terms:
                terms.append(term)
        else:
            for code in sorted(cat.kamus[m["phrase"]]["wilayah"]):
                if code not in regions:
                    regions.append(code)

    period, unresolved, period_tokens = _extract_period(tokens)
    consumed |= period_tokens
    non_term |= period_tokens

    # operation (K-02: outside indicator/region spans) and ranking
    operation, direction = "NONE", None
    free = [i for i in range(len(tokens)) if i not in consumed]
    rank_phrases = sorted(((tuple(p.split()), d) for d, ps in cfg["rank_words"].items() for p in ps),
                          key=lambda x: -len(x[0]))
    rank_used: set[int] = set()
    for phrase, d in rank_phrases:
        for s, e in _find_spans(tokens, phrase):
            if all(i not in non_term and i not in rank_used for i in range(s, e)):
                direction = direction or d
                rank_used |= set(range(s, e))
    if direction:
        operation = "RANK"
    else:
        for phrase, op in sorted(cat.operations.items(), key=lambda x: -len(x[0])):
            if any(all(i in free for i in range(s, e)) for s, e in _find_spans(tokens, phrase)):
                operation = op
                break
    top_n = 1
    words = cfg.get("number_words") or {}
    for i, t in enumerate(tokens[:-1]):
        n = int(t) if t.isdigit() and len(t) <= 2 else words.get(t)
        if n and tokens[i + 1] == "provinsi" and n >= 1:
            top_n = n
            consumed.add(i)
    consumed |= rank_used

    # places named after the preposition but not found in the catalog
    prep, stop = cfg["place_preposition"], set(cfg["place_stop_words"])
    for i, t in enumerate(tokens):
        if t != prep:
            continue
        j, words = i + 1, []
        while j < len(tokens) and len(words) < 3:
            w = tokens[j]
            if j in consumed or w.isdigit() or w in MONTHS or w in stop or w == prep:
                break
            words.append(w)
            j += 1
        if words:
            unresolved.append(" ".join(words))

    return ExtractionResult(raw_question=question, terms=terms, regions=regions, period=period,
                            operation=operation, rank_direction=direction, top_n=top_n, unresolved=unresolved)
