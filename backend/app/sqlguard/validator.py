"""Validator sqlglot (langkah 4, validasi deterministik): satu pernyataan SELECT, hanya tabel skema,
:indikator sebagai parameter pada AST, tanpa DDL/DML/PRAGMA/ATTACH, tanpa fungsi di luar daftar putih.

Kontrak SQL-A/OUT-A (D06, PROPOSED K-03/K-04, belum dibekukan):
- parameter terikat: :indikator (wajib), :periode, :wilayah_0..:wilayah_n
- kolom keluaran hanya `wilayah`, `periode`, `nilai` (alias baku); wajib beralias
"""
from __future__ import annotations

import re

import sqlglot
import sqlglot.expressions as exp
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.qualify import qualify

from backend.app.sqlguard.schema import SQL_SCHEMA

ALLOWED_TABLES = {"provinsi", "indikator", "nilai_indikator"}
ALLOWED_FUNCS = (exp.Sum, exp.Avg, exp.Min, exp.Max, exp.Count)
ALLOWED_OUTPUT = {"wilayah", "periode", "nilai"}
_PARAM = re.compile(r"^(indikator|periode|wilayah_\d+)$")


def _region_target_ok(p: exp.Placeholder, aliases: dict[str, str]) -> bool:
    """M5@314076f: region bindings contain codes, never province names."""
    node = p.parent
    while isinstance(node, (exp.Paren, exp.Tuple)):
        node = node.parent
    if isinstance(node, exp.In):
        col = node.this
    elif isinstance(node, exp.EQ):
        col = node.expression if node.this is p or p in node.this.walk() else node.this
    else:
        return False
    if not isinstance(col, exp.Column):
        return False
    table = aliases.get(col.table, col.table) if col.table else ""
    if col.name == "kode_provinsi":
        return table in ("", "nilai_indikator")
    return col.name == "kode" and table == "provinsi"


def _shape_error(root: exp.Select, op: str, direction: str | None, top_n: int) -> str | None:
    """M5@314076f: enforce the supplied S1 shape, without rewriting SQL."""
    aggs = list(root.find_all(exp.AggFunc))
    group, order, limit = root.args.get("group"), root.args.get("order"), root.args.get("limit")
    if op in ("SUM", "AVG"):
        want = exp.Sum if op == "SUM" else exp.Avg
        if len(aggs) != 1 or not isinstance(aggs[0], want):
            return f"bentuk SQL: harus tepat satu {op}"
        if group or order or limit or any(e.alias_or_name == "wilayah" for e in root.expressions):
            return f"bentuk SQL: {op} tanpa kolom wilayah, GROUP BY, ORDER BY, dan LIMIT"
        return None
    if aggs:
        return "bentuk SQL: tanpa fungsi agregat"
    if group:
        return "bentuk SQL: tanpa GROUP BY"
    if op != "RANK":
        return "bentuk SQL: tanpa LIMIT" if limit else None
    keys = order.expressions if order else []
    if len(keys) != 1 or not isinstance(keys[0].this, exp.Column) or keys[0].this.name != "nilai":
        return "bentuk SQL: RANK wajib ORDER BY nilai"
    if bool(keys[0].args.get("desc")) != (direction == "highest"):
        return "bentuk SQL: arah ORDER BY tidak sesuai ekstraksi"
    n = limit.args.get("expression") if limit else None
    if not isinstance(n, exp.Literal) or n.is_string or str(n.this) != str(top_n):
        return f"bentuk SQL: RANK wajib LIMIT {top_n}"
    return None


def validate_sql(sql: str, forbidden_literals: set[str] | None = None,
                 region_count: int | None = None,
                 shape: tuple[str, str | None, int] | None = None) -> tuple[bool, str | None]:
    try:
        statements = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
    except SqlglotError as exc:
        return False, f"tidak dapat diurai SQLite: {str(exc)[:80]}"
    if len(statements) != 1:
        return False, "harus tepat satu pernyataan"
    root = statements[0]
    if not isinstance(root, exp.Select):
        return False, f"bukan SELECT ({type(root).__name__})"
    ctes = {c.alias for c in root.find_all(exp.CTE)}
    for t in root.find_all(exp.Table):
        if t.db or t.catalog:
            return False, "akses database lain tidak diizinkan"
        if t.name not in ALLOWED_TABLES and t.name not in ctes:
            return False, f"tabel tidak diizinkan: {t.name}"
    for f in root.find_all(exp.Func):
        if not isinstance(f, ALLOWED_FUNCS + (exp.Connector,)):          # And/Or adalah Func pada sqlglot ini
            return False, f"fungsi tidak diizinkan: {f.sql('sqlite')[:30]}"
    if next(root.find_all(exp.Window), None) is not None:
        return False, "fungsi window tidak diizinkan"
    params = set()
    for p in root.find_all(exp.Placeholder):
        name = str(p.this)
        if not _PARAM.match(name):
            return False, f"parameter tidak dikenal: :{name}"
        params.add(name)
    if any(isinstance(n, (exp.Parameter,)) for n in root.walk()):
        return False, "parameter gaya lain tidak diizinkan"
    if "indikator" not in params:
        return False, "tidak memuat parameter :indikator"
    if forbidden_literals:
        low = {x.casefold() for x in forbidden_literals}
        for lit in root.find_all(exp.Literal):
            if lit.is_string and lit.this.casefold() in low:
                return False, "kode indikator tidak boleh ditulis literal"
    # Team K-03 (reference D13, 20 Oct): text values are bound, and every
    # extracted region has exactly one declared scalar binding.
    if any(literal.is_string for literal in root.find_all(exp.Literal)):
        return False, "literal teks tidak diizinkan; gunakan parameter"
    aliases = {t.alias_or_name: t.name for t in root.find_all(exp.Table)}
    for p in root.find_all(exp.Placeholder):
        if str(p.this).startswith("wilayah_") and not _region_target_ok(p, aliases):
            return False, "parameter wilayah hanya boleh dibandingkan dengan kode provinsi"
    if region_count is not None:
        expected = {f"wilayah_{i}" for i in range(region_count)}
        used = {name for name in params if name.startswith("wilayah_")}
        if used != expected:
            return False, "parameter wilayah tidak sesuai ekstraksi"
    if shape is not None:
        why = _shape_error(root, *shape)
        if why:
            return False, why
    if not root.expressions:
        return False, "tanpa kolom keluaran"
    for e in root.expressions:
        if isinstance(e, exp.Star) or e.alias_or_name == "":
            return False, "kolom keluaran wajib beralias (wilayah, periode, atau nilai)"
        if e.alias_or_name not in ALLOWED_OUTPUT:
            return False, f"alias keluaran tidak baku: {e.alias_or_name}"
    try:
        # Qualify a copy for schema checks only. Never repair or replace model SQL.
        qualify(root.copy(), dialect="sqlite", schema=SQL_SCHEMA, expand_stars=False)
    except SqlglotError as exc:
        return False, f"kolom atau alias tidak sesuai skema: {str(exc)[:100]}"
    return True, None
