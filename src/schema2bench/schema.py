from __future__ import annotations

import random
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    type: str
    notnull: bool
    pk: bool
    samples: tuple[Any, ...] = ()


@dataclass(frozen=True)
class TableInfo:
    name: str
    columns: tuple[ColumnInfo, ...]
    row_count: int


@dataclass(frozen=True)
class JoinEdge:
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    source: str


@dataclass
class SchemaProfile:
    db_path: Path
    tables: dict[str, TableInfo]
    join_edges: list[JoinEdge] = field(default_factory=list)

    def table_names(self) -> list[str]:
        return list(self.tables)

    def numeric_columns(self, table: str) -> list[ColumnInfo]:
        return [c for c in self.tables[table].columns if is_numeric_type(c.type)]

    def measure_columns(self, table: str) -> list[ColumnInfo]:
        return [c for c in self.numeric_columns(table) if is_semantic_measure(c)]

    def text_columns(self, table: str) -> list[ColumnInfo]:
        return [c for c in self.tables[table].columns if not is_numeric_type(c.type)]

    def any_columns(self, table: str) -> list[ColumnInfo]:
        return list(self.tables[table].columns)

    def edges_for_table(self, table: str) -> list[JoinEdge]:
        return [e for e in self.join_edges if e.left_table == table or e.right_table == table]


def is_numeric_type(sql_type: str) -> bool:
    t = (sql_type or "").lower()
    return any(x in t for x in ("int", "real", "float", "double", "numeric", "decimal"))


MEASURE_HINTS = {
    "amount",
    "amt",
    "balance",
    "bytes",
    "charge",
    "cost",
    "count",
    "credit",
    "discount",
    "distance",
    "duration",
    "employees",
    "estimate",
    "fee",
    "humidity",
    "income",
    "length",
    "loss",
    "milliseconds",
    "miles",
    "paid",
    "percentage",
    "pressure",
    "price",
    "profit",
    "quantity",
    "qty",
    "rating",
    "revenue",
    "runtime",
    "sales",
    "score",
    "severity",
    "size",
    "speed",
    "space",
    "sqft",
    "tax",
    "temperature",
    "total",
    "value",
    "visibility",
    "votes",
    "weight",
}


KEY_SUFFIXES = {"id", "key", "sk", "const"}
ROLE_TOKENS = {
    "access",
    "bill",
    "billing",
    "close",
    "closed",
    "creation",
    "current",
    "first",
    "open",
    "refunded",
    "returned",
    "returning",
    "ship",
    "shipto",
    "sold",
}


def identifier_tokens(name: str) -> list[str]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return [token for token in re.split(r"[^a-z0-9]+", expanded.lower()) if token]


def key_entity(name: str) -> str | None:
    tokens = identifier_tokens(name)
    if not tokens:
        return None
    last = tokens[-1]
    if last in {"nconst", "tconst"}:
        return last
    if last not in KEY_SUFFIXES:
        for suffix in ("const", "key", "id"):
            if last.endswith(suffix) and len(last) > len(suffix):
                entity = last[: -len(suffix)]
                return {"addr": "address", "cust": "customer", "supp": "supplier"}.get(entity, entity)
        return None
    if len(tokens) >= 3 and tokens[-2] == "demo" and tokens[-3] in {"cd", "hd"}:
        return f"{tokens[-3]}emo"
    stem = [token for token in tokens[:-1] if token not in ROLE_TOKENS]
    if not stem:
        return None
    if len(stem) > 1 and len(stem[0]) <= 3:
        stem = stem[1:]
    aliases = {"addr": "address", "cust": "customer", "supp": "supplier", "promo": "promotion"}
    return "_".join(aliases.get(token, token) for token in stem)


def column_represents_table(table: str, column: str) -> bool:
    entity = key_entity(column)
    if not entity:
        return False
    table_tokens = identifier_tokens(table)
    if not table_tokens:
        return False
    table_entity = table_tokens[-1].rstrip("s")
    entity = entity.rstrip("s")
    return table_entity.startswith(entity) or entity.startswith(table_entity)


def is_identifier_like(column: ColumnInfo) -> bool:
    if column.pk or key_entity(column.name):
        return True
    low = column.name.lower()
    return low.endswith(("_number", "number")) and any(
        token in low for token in ("order", "ticket", "line", "catalog")
    )


def is_semantic_measure(column: ColumnInfo) -> bool:
    if not is_numeric_type(column.type) or is_identifier_like(column):
        return False
    tokens = set(identifier_tokens(column.name))
    compact = "".join(tokens)
    return bool(tokens & MEASURE_HINTS) or any(hint in compact for hint in MEASURE_HINTS)


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class SchemaProfilerAgent:
    def __init__(
        self,
        sample_values_per_column: int = 5,
        max_tables: int | None = None,
        count_rows: bool = False,
        enhanced_join_inference: bool = False,
    ):
        self.sample_values_per_column = sample_values_per_column
        self.max_tables = max_tables
        self.count_rows = count_rows
        self.enhanced_join_inference = enhanced_join_inference

    def profile(self, db_path: str | Path) -> SchemaProfile:
        path = Path(db_path).resolve()
        con = sqlite3.connect(path)
        con.row_factory = sqlite3.Row
        try:
            table_rows = con.execute(
                "select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name"
            ).fetchall()
            table_names = [r["name"] for r in table_rows]
            if self.max_tables:
                table_names = table_names[: self.max_tables]
            tables: dict[str, TableInfo] = {}
            for table in table_names:
                columns = self._columns(con, table)
                row_count = self._row_count(con, table)
                tables[table] = TableInfo(table, tuple(columns), row_count)
            edges = self._foreign_key_edges(con, table_names)
            edges.extend(self._inferred_edges(tables, edges))
            return SchemaProfile(path, tables, edges)
        finally:
            con.close()

    def _columns(self, con: sqlite3.Connection, table: str) -> list[ColumnInfo]:
        rows = con.execute(f"pragma table_info({quote_ident(table)})").fetchall()
        cols = []
        for r in rows:
            name = r["name"]
            samples = self._sample_values(con, table, name)
            cols.append(ColumnInfo(name=name, type=r["type"] or "", notnull=bool(r["notnull"]), pk=bool(r["pk"]), samples=tuple(samples)))
        return cols

    def _row_count(self, con: sqlite3.Connection, table: str) -> int:
        if not self.count_rows:
            return 1
        try:
            return int(con.execute(f"select count(*) from {quote_ident(table)}").fetchone()[0])
        except sqlite3.Error:
            return 0

    def _sample_values(self, con: sqlite3.Connection, table: str, column: str) -> list[Any]:
        try:
            rows = con.execute(
                f"select distinct {quote_ident(column)} from "
                f"(select {quote_ident(column)} from {quote_ident(table)} limit 5000) "
                f"where {quote_ident(column)} is not null limit {int(self.sample_values_per_column)}"
            ).fetchall()
            return [r[0] for r in rows]
        except sqlite3.Error:
            return []

    def _foreign_key_edges(self, con: sqlite3.Connection, table_names: list[str]) -> list[JoinEdge]:
        edges: list[JoinEdge] = []
        for table in table_names:
            try:
                rows = con.execute(f"pragma foreign_key_list({quote_ident(table)})").fetchall()
            except sqlite3.Error:
                continue
            for r in rows:
                ref_table = r["table"]
                if ref_table in table_names:
                    edges.append(JoinEdge(table, r["from"], ref_table, r["to"], "foreign_key"))
        return edges

    def _inferred_edges(self, tables: dict[str, TableInfo], existing: list[JoinEdge]) -> list[JoinEdge]:
        seen = {(e.left_table, e.left_column, e.right_table, e.right_column) for e in existing}
        inferred: list[JoinEdge] = []
        table_items = list(tables.items())
        for left_name, left in table_items:
            for right_name, right in table_items:
                if left_name >= right_name:
                    continue
                for lc in left.columns:
                    for rc in right.columns:
                        if not self._columns_can_join(left_name, lc, right_name, rc):
                            continue
                        key = (left_name, lc.name, right_name, rc.name)
                        if key not in seen:
                            inferred.append(JoinEdge(left_name, lc.name, right_name, rc.name, "inferred_name"))
                            seen.add(key)
        return inferred

    def _columns_can_join(self, left_table: str, left_col: ColumnInfo, right_table: str, right_col: ColumnInfo) -> bool:
        l = left_col.name.lower()
        r = right_col.name.lower()
        lt = left_table.lower()
        rt = right_table.lower()
        if l == r and (l.endswith("_id") or l.endswith("_sk") or l.endswith("const") or l.endswith("key") or l == "id"):
            return True
        if l in {f"{rt}_id", f"{rt}_sk", f"{rt.rstrip('s')}_id", f"{rt.rstrip('s')}_sk"} and (r == "id" or r.endswith("_id") or r.endswith("_sk")):
            return True
        if r in {f"{lt}_id", f"{lt}_sk", f"{lt.rstrip('s')}_id", f"{lt.rstrip('s')}_sk"} and (l == "id" or l.endswith("_id") or l.endswith("_sk")):
            return True
        if not self.enhanced_join_inference:
            return False
        if is_numeric_type(left_col.type) != is_numeric_type(right_col.type):
            return False
        left_entity = key_entity(left_col.name)
        right_entity = key_entity(right_col.name)
        if not left_entity or left_entity != right_entity:
            return False
        if not (
            left_col.pk
            or right_col.pk
            or column_represents_table(left_table, left_col.name)
            or column_represents_table(right_table, right_col.name)
        ):
            return False
        return True


def choose_table(profile: SchemaProfile, rng: random.Random, min_rows: int = 1) -> str:
    candidates = [t.name for t in profile.tables.values() if t.row_count >= min_rows and t.columns]
    if not candidates:
        candidates = [t.name for t in profile.tables.values() if t.columns]
    return rng.choice(candidates)
