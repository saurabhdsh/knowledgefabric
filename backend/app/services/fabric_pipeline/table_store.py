"""Queryable table store: one SQLite file per fabric (Release 2.0, Phase 1).

Rows of a tabular fabric live here, typed and indexed, instead of being turned
into text chunks. Counts, sums, filters and joins are answered by SQL over the
full data; identifiers are looked up exactly and expanded through the profiled
foreign keys.

Queries run on a read-only connection with a statement authorizer that allows
only SELECT, a row cap and a time limit.
"""
from __future__ import annotations

import logging
import os
import re
import sqlite3
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.core.config import settings
from app.services.fabric_pipeline.tabular_profiler import normalize_value

logger = logging.getLogger(__name__)

_SQL_TYPES = {
    "integer": "INTEGER",
    "float": "REAL",
    "boolean": "INTEGER",
    "date": "TEXT",
    "datetime": "TEXT",
    "string": "TEXT",
    "json": "TEXT",
}

_RESERVED = {
    "abort", "action", "add", "after", "all", "alter", "analyze", "and", "as", "asc", "attach",
    "autoincrement", "before", "begin", "between", "by", "cascade", "case", "cast", "check",
    "collate", "column", "commit", "conflict", "constraint", "create", "cross", "current",
    "current_date", "current_time", "current_timestamp", "database", "default", "deferrable",
    "deferred", "delete", "desc", "detach", "distinct", "do", "drop", "each", "else", "end",
    "escape", "except", "exclusive", "exists", "explain", "fail", "filter", "first", "following",
    "for", "foreign", "from", "full", "glob", "group", "groups", "having", "if", "ignore",
    "immediate", "in", "index", "indexed", "initially", "inner", "insert", "instead", "intersect",
    "into", "is", "isnull", "join", "key", "last", "left", "like", "limit", "match", "natural",
    "no", "not", "nothing", "notnull", "null", "nulls", "of", "offset", "on", "or", "order",
    "others", "outer", "over", "partition", "plan", "pragma", "preceding", "primary", "query",
    "raise", "range", "recursive", "references", "regexp", "reindex", "release", "rename",
    "replace", "restrict", "right", "rollback", "row", "rows", "savepoint", "select", "set",
    "table", "temp", "temporary", "then", "ties", "to", "transaction", "trigger", "unbounded",
    "union", "unique", "update", "using", "vacuum", "values", "view", "virtual", "when", "where",
    "window", "with", "without",
}

_FORBIDDEN_WORDS = (
    "insert", "update", "delete", "drop", "alter", "create", "attach", "detach", "pragma",
    "vacuum", "replace", "reindex", "analyze", "begin", "commit", "rollback", "savepoint",
    "release", "load_extension",
)


class SqlNotAllowedError(ValueError):
    """The statement is not a single read-only SELECT."""


class TableStoreError(RuntimeError):
    pass


def sql_identifier(name: str, fallback: str = "col") -> str:
    """Stable, unquoted-safe SQL name for a table or column."""
    cleaned = re.sub(r"[^0-9a-zA-Z_]+", "_", str(name or "").strip()).strip("_").lower()
    if not cleaned:
        cleaned = fallback
    if cleaned[0].isdigit():
        cleaned = f"{fallback[0]}_{cleaned}"
    if cleaned in _RESERVED:
        cleaned = f"{cleaned}_"
    return cleaned


def assign_sql_names(profile: Dict[str, Any]) -> None:
    """Add ``sql_name`` to every table and column of a profile (in place, unique)."""
    used_tables: set = set()
    for table in profile.get("tables", []):
        base = sql_identifier(table["name"], "table")
        name, n = base, 2
        while name in used_tables:
            name, n = f"{base}_{n}", n + 1
        used_tables.add(name)
        table["sql_name"] = name
        used_cols: set = set()
        for col in table["columns"]:
            cbase = sql_identifier(col["name"], "col")
            cname, k = cbase, 2
            while cname in used_cols:
                cname, k = f"{cbase}_{k}", k + 1
            used_cols.add(cname)
            col["sql_name"] = cname


def _strip_literals_and_comments(sql: str) -> str:
    out = re.sub(r"--[^\n]*", " ", sql)
    out = re.sub(r"/\*.*?\*/", " ", out, flags=re.S)
    out = re.sub(r"'(?:[^']|'')*'", "''", out)
    out = re.sub(r'"(?:[^"]|"")*"', '""', out)
    return out


def validate_select(sql: str) -> str:
    """Return the statement if it is one read-only SELECT; raise otherwise."""
    statement = (sql or "").strip()
    while statement.endswith(";"):
        statement = statement[:-1].rstrip()
    if not statement:
        raise SqlNotAllowedError("Empty SQL statement")
    bare = _strip_literals_and_comments(statement)
    if ";" in bare:
        raise SqlNotAllowedError("Only a single statement is allowed")
    first = re.match(r"\s*\(*\s*([a-zA-Z]+)", bare)
    if not first or first.group(1).lower() not in ("select", "with"):
        raise SqlNotAllowedError("Only SELECT statements are allowed")
    lowered = bare.lower()
    for word in _FORBIDDEN_WORDS:
        if re.search(rf"\b{word}\b", lowered):
            raise SqlNotAllowedError(f"'{word.upper()}' is not allowed in a read-only query")
    return statement


def _authorizer(action: int, arg1: Any, arg2: Any, db_name: Any, trigger: Any) -> int:
    allowed = {
        getattr(sqlite3, "SQLITE_SELECT", 21),
        getattr(sqlite3, "SQLITE_READ", 20),
        getattr(sqlite3, "SQLITE_FUNCTION", 31),
        getattr(sqlite3, "SQLITE_RECURSIVE", 33),
    }
    if action not in allowed:
        return sqlite3.SQLITE_DENY
    if action == getattr(sqlite3, "SQLITE_FUNCTION", 31) and str(arg2 or "").lower() == "load_extension":
        return sqlite3.SQLITE_DENY
    if action == getattr(sqlite3, "SQLITE_READ", 20) and str(arg1 or "").lower().startswith("sqlite_"):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


class TableStore:
    def __init__(self, root: Optional[str] = None) -> None:
        self._root = root

    @property
    def root(self) -> str:
        root = self._root or settings.FABRIC_TABLES_DIR
        os.makedirs(root, exist_ok=True)
        return root

    def path(self, fabric_id: str) -> str:
        safe = re.sub(r"[^0-9a-zA-Z_.-]", "_", fabric_id)
        return os.path.join(self.root, f"{safe}.sqlite")

    def exists(self, fabric_id: str) -> bool:
        return bool(fabric_id) and os.path.isfile(self.path(fabric_id))

    def delete(self, fabric_id: str) -> bool:
        removed = False
        for suffix in ("", ".tmp", "-wal", "-shm"):
            p = self.path(fabric_id) + suffix
            if os.path.exists(p):
                os.remove(p)
                removed = True
        return removed

    # ------------------------------------------------------------------ build

    def build(
        self,
        fabric_id: str,
        tables: Dict[str, List[Dict[str, Any]]],
        profile: Dict[str, Any],
    ) -> Dict[str, int]:
        """Create the store from raw rows using the profiled types.

        Written to a temporary file and swapped in, so a failed build never
        leaves a half-written store. Returns rows stored per table.
        """
        if not all("sql_name" in t for t in profile.get("tables", [])):
            assign_sql_names(profile)
        final_path = self.path(fabric_id)
        tmp_path = final_path + ".tmp"
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

        stored: Dict[str, int] = {}
        conn = sqlite3.connect(tmp_path)
        try:
            conn.execute("PRAGMA journal_mode=OFF")
            conn.execute("PRAGMA synchronous=OFF")
            fk_columns = {
                (fk["from_table"], fk["from_column"]) for fk in profile.get("foreign_keys", [])
            }
            for table in profile["tables"]:
                rows = tables.get(table["name"]) or []
                cols = table["columns"]
                if not cols:
                    stored[table["name"]] = 0
                    continue
                col_defs = ", ".join(
                    f'"{c["sql_name"]}" {_SQL_TYPES.get(c["type"], "TEXT")}' for c in cols
                )
                conn.execute(f'CREATE TABLE "{table["sql_name"]}" ({col_defs})')
                placeholders = ", ".join("?" for _ in cols)
                insert = f'INSERT INTO "{table["sql_name"]}" VALUES ({placeholders})'
                batch: List[Tuple[Any, ...]] = []
                for row in rows:
                    batch.append(tuple(normalize_value(row.get(c["name"]), c["type"], c) for c in cols))
                    if len(batch) >= 5000:
                        conn.executemany(insert, batch)
                        batch = []
                if batch:
                    conn.executemany(insert, batch)
                stored[table["name"]] = len(rows)

                by_name = {c["name"]: c for c in cols}
                pk = [by_name[n]["sql_name"] for n in table.get("primary_key") or [] if n in by_name]
                if pk:
                    cols_sql = ", ".join(f'"{c}"' for c in pk)
                    conn.execute(
                        f'CREATE UNIQUE INDEX "ux_{table["sql_name"]}_pk" ON "{table["sql_name"]}" ({cols_sql})'
                    )
                for c in cols:
                    if (table["name"], c["name"]) in fk_columns and [c["name"]] != (table.get("primary_key") or []):
                        conn.execute(
                            f'CREATE INDEX "ix_{table["sql_name"]}_{c["sql_name"]}" '
                            f'ON "{table["sql_name"]}" ("{c["sql_name"]}")'
                        )
            conn.commit()
        except Exception:
            conn.close()
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
        conn.close()
        os.replace(tmp_path, final_path)
        return stored

    # ------------------------------------------------------------------ query

    def _connect_readonly(self, fabric_id: str) -> sqlite3.Connection:
        path = self.path(fabric_id)
        if not os.path.isfile(path):
            raise TableStoreError(f"No table store for fabric '{fabric_id}'")
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        conn.execute("PRAGMA query_only=ON")
        return conn

    def query(
        self,
        fabric_id: str,
        sql: str,
        params: Sequence[Any] = (),
        *,
        max_rows: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Run one read-only SELECT. Returns columns, rows (lists) and ``truncated``."""
        statement = validate_select(sql)
        limit = max_rows if max_rows is not None else settings.FABRIC_SQL_MAX_ROWS
        timeout = timeout_seconds if timeout_seconds is not None else settings.FABRIC_SQL_TIMEOUT_SECONDS
        conn = self._connect_readonly(fabric_id)
        deadline = time.time() + timeout
        try:
            conn.set_authorizer(_authorizer)
            conn.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 10000)
            try:
                cursor = conn.execute(statement, tuple(params))
            except sqlite3.DatabaseError as exc:
                if "not authorized" in str(exc).lower():
                    raise SqlNotAllowedError("Only read-only SELECT statements are allowed") from exc
                raise
            columns = [d[0] for d in (cursor.description or [])]
            try:
                fetched = cursor.fetchmany(limit + 1)
            except sqlite3.OperationalError as exc:
                if "interrupt" in str(exc).lower():
                    raise TableStoreError(f"Query exceeded the {timeout:g}s time limit") from exc
                raise
            truncated = len(fetched) > limit
            return {
                "columns": columns,
                "rows": [list(r) for r in fetched[:limit]],
                "truncated": truncated,
                "row_limit": limit,
            }
        except sqlite3.OperationalError as exc:
            if "interrupt" in str(exc).lower():
                raise TableStoreError(f"Query exceeded the {timeout:g}s time limit") from exc
            raise
        finally:
            conn.close()

    def table_names(self, fabric_id: str) -> List[str]:
        conn = self._connect_readonly(fabric_id)
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
            return [r[0] for r in rows]
        finally:
            conn.close()

    def row_counts(self, fabric_id: str) -> Dict[str, int]:
        conn = self._connect_readonly(fabric_id)
        try:
            names = [
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            ]
            return {n: conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}
        finally:
            conn.close()

    def iter_rows(
        self,
        fabric_id: str,
        table_sql_name: str,
        *,
        limit: Optional[int] = None,
        offset: int = 0,
        batch: int = 2000,
    ) -> Iterable[Dict[str, Any]]:
        """Yield rows of one table as dicts keyed by SQL column name."""
        conn = self._connect_readonly(fabric_id)
        try:
            sql = f'SELECT * FROM "{table_sql_name}"'
            if limit is not None:
                sql += f" LIMIT {int(limit)} OFFSET {int(offset)}"
            elif offset:
                sql += f" LIMIT -1 OFFSET {int(offset)}"
            cursor = conn.execute(sql)
            columns = [d[0] for d in cursor.description]
            while True:
                chunk = cursor.fetchmany(batch)
                if not chunk:
                    break
                for row in chunk:
                    yield dict(zip(columns, row))
        finally:
            conn.close()

    def rows(self, fabric_id: str, table_sql_name: str, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        return list(self.iter_rows(fabric_id, table_sql_name, limit=limit, offset=offset))

    def apply_row_delta(
        self,
        fabric_id: str,
        table_sql_name: str,
        columns: Sequence[str],
        key_columns: Sequence[str],
        plan: Dict[str, Any],
    ) -> Dict[str, int]:
        """Apply an incremental plan (added/changed/removed) to one stored table.

        ``columns`` and ``key_columns`` are SQL column names. Row dicts use those names.
        A plan whose mode is not ``incremental`` is refused.
        """
        if plan.get("mode") != "incremental":
            raise TableStoreError(plan.get("reason") or "incremental apply refused")
        if not self.exists(fabric_id):
            raise TableStoreError(f"No table store for fabric '{fabric_id}'")
        conn = sqlite3.connect(self.path(fabric_id))
        try:
            where = " AND ".join(f'"{k}" = ?' for k in key_columns)
            for row in plan.get("removed") or []:
                conn.execute(
                    f'DELETE FROM "{table_sql_name}" WHERE {where}',
                    [row.get(k) for k in key_columns],
                )
            non_keys = [c for c in columns if c not in key_columns]
            if non_keys:
                sets = ", ".join(f'"{c}" = ?' for c in non_keys)
                for row in plan.get("changed") or []:
                    conn.execute(
                        f'UPDATE "{table_sql_name}" SET {sets} WHERE {where}',
                        [row.get(c) for c in non_keys] + [row.get(k) for k in key_columns],
                    )
            placeholders = ", ".join("?" for _ in columns)
            col_sql = ", ".join(f'"{c}"' for c in columns)
            insert = f'INSERT INTO "{table_sql_name}" ({col_sql}) VALUES ({placeholders})'
            for row in plan.get("added") or []:
                conn.execute(insert, [row.get(c) for c in columns])
            conn.commit()
        finally:
            conn.close()
        return {
            "added": len(plan.get("added") or []),
            "changed": len(plan.get("changed") or []),
            "removed": len(plan.get("removed") or []),
        }

    def original_rows(
        self,
        fabric_id: str,
        profile: Dict[str, Any],
        *,
        table: Optional[str] = None,
        limit_per_table: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Rows keyed by original column names, stamped with ``__source_collection``.

        This is the shape the rule-based analytics engine and the graph sample
        enrichment expect.
        """
        out: List[Dict[str, Any]] = []
        for t in profile.get("tables", []):
            if table and t["name"] != table:
                continue
            mapping = {c["sql_name"]: c for c in t["columns"]}
            for row in self.iter_rows(fabric_id, t["sql_name"], limit=limit_per_table):
                item: Dict[str, Any] = {}
                for sql_name, value in row.items():
                    col = mapping.get(sql_name)
                    if col is None:
                        continue
                    if col["type"] == "boolean" and value is not None:
                        value = bool(value)
                    item[col["name"]] = value
                item["__source_collection"] = t["name"]
                out.append(item)
        return out


table_store = TableStore()
