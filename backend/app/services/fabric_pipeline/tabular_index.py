"""What a tabular fabric puts in the vector index (Release 2.0, Phase 1).

Rows are not embedded. The index holds only what semantic search is good at:

* a dataset card and one schema card per table (so questions find the right table),
* one summary per entity row (who/what it is, its attributes, what it links to
  and how many related rows it has),
* long free-text columns (notes, narratives).

Numbers and filters are answered from the table store, not from these chunks.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.core.config import settings
from app.services.fabric_pipeline.table_store import TableStore
from app.services.fabric_pipeline.tabular_profiler import _MONEY_NAME_RE, table_by_name

MAX_ATTRS_IN_SUMMARY = 24
MAX_VALUE_CHARS = 160


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:,.2f}" if abs(value) >= 1000 else f"{value:g}"
    text = str(value)
    return text if len(text) <= MAX_VALUE_CHARS else text[: MAX_VALUE_CHARS - 1] + "…"


def _humanize(name: str) -> str:
    return re.sub(r"[_\-]+", " ", name).strip()


def _singular_label(table_name: str) -> str:
    words = _humanize(table_name).split()
    if not words:
        return "record"
    last = words[-1]
    if last.endswith("ies") and len(last) > 4:
        last = last[:-3] + "y"
    elif last.endswith("ses") and len(last) > 4:
        last = last[:-2]
    elif last.endswith("s") and not last.endswith("ss") and len(last) > 3:
        last = last[:-1]
    words[-1] = last
    return " ".join(words)


def dataset_card(profile: Dict[str, Any], fabric_name: str) -> str:
    lines = [f"Dataset: {fabric_name}", "Tables:"]
    for t in profile["tables"]:
        note = ""
        if t.get("is_sample"):
            note = f" (sample of {t['source_row_count']:,} source rows)"
        key = ", ".join(t["primary_key"]) or "none"
        lines.append(f"- {t['name']}: {t['row_count']:,} rows{note}; {t['kind']}; key: {key}")
    if profile.get("foreign_keys"):
        lines.append("Relationships:")
        for fk in profile["foreign_keys"]:
            lines.append(
                f"- {fk['from_table']}.{fk['from_column']} -> {fk['to_table']}.{fk['to_column']} "
                f"({fk['cardinality']})"
            )
    for fk in profile.get("composite_foreign_keys") or []:
        if not profile.get("foreign_keys"):
            lines.append("Relationships:")
        lines.append(
            f"- {fk['from_table']}.({', '.join(fk['from_columns'])}) -> "
            f"{fk['to_table']}.({', '.join(fk['to_columns'])}) ({fk['cardinality']}, two-column key)"
        )
    return "\n".join(lines)


def schema_card(table: Dict[str, Any], profile: Dict[str, Any], *, for_sql: bool = False) -> str:
    """Describe one table. ``for_sql=True`` uses SQL names (for the query planner)."""
    tname = table["sql_name"] if for_sql else table["name"]
    head = f"Table {tname}: {table['row_count']:,} rows"
    if table.get("is_sample"):
        head += f" (sample of {table['source_row_count']:,} rows in the source)"
    head += f"; kind: {table['kind']}"
    lines = [head]
    if table["primary_key"]:
        by_name = {c["name"]: c for c in table["columns"]}
        pk = [by_name[n]["sql_name"] if for_sql else n for n in table["primary_key"]]
        lines.append(f"Primary key: {', '.join(pk)}")
    lines.append("Columns:")
    for c in table["columns"]:
        cname = c["sql_name"] if for_sql else c["name"]
        parts = [f"- {cname} ({c['type']}"]
        if c["type"] == "boolean":
            parts[0] += ", stored as 1/0"
        if c["type"] in ("date", "datetime"):
            parts[0] += ", ISO text"
        parts[0] += f"; {c['role']})"
        if c["null_rate"] > 0:
            parts.append(f"{c['null_rate']:.0%} empty")
        if c["type"] in ("integer", "float") and "min" in c and c["role"] == "measure":
            parts.append(f"range {_fmt(c['min'])} to {_fmt(c['max'])}")
        elif c["type"] in ("date", "datetime") and "min" in c:
            parts.append(f"{c['min']} to {c['max']}")
        elif c["role"] == "category" and c["sample_values"]:
            shown = ", ".join(_fmt(v) for v in c["sample_values"][:8])
            more = "" if c["distinct_count"] <= 8 else f" (+{c['distinct_count'] - 8} more)"
            parts.append(f"values: {shown}{more}")
        elif c["sample_values"] and c["role"] != "text":
            parts.append("e.g. " + ", ".join(_fmt(v) for v in c["sample_values"][:3]))
        lines.append("; ".join(parts))
    out_fks = [fk for fk in profile.get("foreign_keys", []) if fk["from_table"] == table["name"]]
    in_fks = [fk for fk in profile.get("foreign_keys", []) if fk["to_table"] == table["name"]]
    pair_fks = [fk for fk in profile.get("composite_foreign_keys") or [] if fk["from_table"] == table["name"]]
    if out_fks or in_fks or pair_fks:
        lines.append("Relationships:")

    def _names(tbl_name: str, col_name: str) -> Tuple[str, str]:
        if not for_sql:
            return tbl_name, col_name
        t = table_by_name(profile, tbl_name)
        col = next(c for c in t["columns"] if c["name"] == col_name)
        return t["sql_name"], col["sql_name"]

    for fk in out_fks:
        ft, fc = _names(fk["from_table"], fk["from_column"])
        tt, tc = _names(fk["to_table"], fk["to_column"])
        lines.append(f"- {ft}.{fc} -> {tt}.{tc} ({fk['cardinality']})")
    for fk in in_fks:
        ft, fc = _names(fk["from_table"], fk["from_column"])
        tt, tc = _names(fk["to_table"], fk["to_column"])
        lines.append(f"- referenced by {ft}.{fc}")
    for fk in pair_fks:
        pairs = []
        for from_col, to_col in zip(fk["from_columns"], fk["to_columns"]):
            ft, fc = _names(fk["from_table"], from_col)
            tt, tc = _names(fk["to_table"], to_col)
            pairs.append(f"{ft}.{fc} = {tt}.{tc}")
        lines.append(f"- two-column key, join on both: {' AND '.join(pairs)} ({fk['cardinality']})")
    return "\n".join(lines)


def sql_schema_text(profile: Dict[str, Any]) -> str:
    """Full schema in SQL names, for the text-to-SQL planner."""
    return "\n\n".join(schema_card(t, profile, for_sql=True) for t in profile["tables"] if t["row_count"])


def _child_aggregates(
    store: TableStore, fabric_id: str, profile: Dict[str, Any], table: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Per incoming FK: counts (and money totals) of child rows grouped by parent key."""
    if len(table["primary_key"]) != 1:
        return []
    pk = table["primary_key"][0]
    out: List[Dict[str, Any]] = []
    for fk in profile.get("foreign_keys", []):
        if fk["to_table"] != table["name"] or fk["to_column"] != pk or fk["from_table"] == table["name"]:
            continue
        child = table_by_name(profile, fk["from_table"])
        if not child or not child["row_count"]:
            continue
        ccol = next(c for c in child["columns"] if c["name"] == fk["from_column"])
        money = [
            c for c in child["columns"]
            if c["role"] == "measure" and _MONEY_NAME_RE.search(c["name"])
        ][:2]
        select = [f'"{ccol["sql_name"]}" AS k', "COUNT(*) AS n"]
        select += [f'SUM("{m["sql_name"]}") AS s{i}' for i, m in enumerate(money)]
        sql = (
            f'SELECT {", ".join(select)} FROM "{child["sql_name"]}" '
            f'WHERE "{ccol["sql_name"]}" IS NOT NULL GROUP BY "{ccol["sql_name"]}"'
        )
        result = store.query(fabric_id, sql, max_rows=10_000_000, timeout_seconds=120)
        by_key = {
            row[0]: {"count": row[1], "sums": {m["name"]: row[2 + i] for i, m in enumerate(money)}}
            for row in result["rows"]
        }
        out.append({"fk": fk, "child": child, "by_key": by_key})
    return out


def _parent_labels(
    store: TableStore, fabric_id: str, profile: Dict[str, Any], table: Dict[str, Any]
) -> Dict[str, Dict[Any, str]]:
    """Per outgoing FK column: parent key -> parent label (when the parent has one)."""
    out: Dict[str, Dict[Any, str]] = {}
    for fk in profile.get("foreign_keys", []):
        if fk["from_table"] != table["name"] or fk["to_table"] == table["name"]:
            continue
        parent = table_by_name(profile, fk["to_table"])
        if not parent or not parent.get("label_column"):
            continue
        pcols = {c["name"]: c for c in parent["columns"]}
        sql = (
            f'SELECT "{pcols[fk["to_column"]]["sql_name"]}", "{pcols[parent["label_column"]]["sql_name"]}" '
            f'FROM "{parent["sql_name"]}"'
        )
        result = store.query(fabric_id, sql, max_rows=10_000_000, timeout_seconds=120)
        out[fk["from_column"]] = {row[0]: row[1] for row in result["rows"] if row[1] is not None}
    return out


def entity_summary(
    row: Dict[str, Any],
    table: Dict[str, Any],
    parent_labels: Dict[str, Dict[Any, str]],
    child_aggs: List[Dict[str, Any]],
) -> Tuple[str, str]:
    """``(row key, summary text)`` for one entity row (row keyed by original column names)."""
    pk = table["primary_key"]
    key = " / ".join(_fmt(row.get(k)) for k in pk) if pk else ""
    label_col = table.get("label_column")
    label = _fmt(row.get(label_col)) if label_col else ""
    noun = _singular_label(table["name"]).capitalize()
    title = f"{noun} {key}".strip()
    if label:
        title += f" ({label})"

    attrs: List[str] = []
    long_text: List[str] = []
    for col in table["columns"]:
        name = col["name"]
        if name in pk or name == label_col:
            continue
        value = row.get(name)
        if value is None or value == "":
            continue
        if col["type"] == "boolean":
            value = "yes" if value else "no"
        if col["role"] == "text":
            long_text.append(f"{_humanize(name)}: {str(value)}")
            continue
        text = f"{_humanize(name)}: {_fmt(value)}"
        if name in parent_labels:
            parent_label = parent_labels[name].get(row.get(name))
            if parent_label:
                text += f" ({parent_label})"
        attrs.append(text)
    lines = [title + "."]
    if attrs:
        shown = attrs[:MAX_ATTRS_IN_SUMMARY]
        lines.append("; ".join(shown) + ".")
    if child_aggs and len(pk) == 1:
        related: List[str] = []
        for agg in child_aggs:
            stats = agg["by_key"].get(row.get(pk[0]))
            if not stats:
                continue
            part = f"{stats['count']} {_humanize(agg['child']['name'])}"
            sums = [
                f"total {_humanize(col)} {_fmt(float(total))}"
                for col, total in stats["sums"].items() if total is not None
            ]
            if sums:
                part += f" ({'; '.join(sums)})"
            related.append(part)
        if related:
            lines.append("Related: " + "; ".join(related) + ".")
    lines.extend(long_text)
    return key, "\n".join(lines)


def build_index_documents(
    fabric_id: str,
    fabric_name: str,
    profile: Dict[str, Any],
    store: TableStore,
    *,
    max_entities_per_table: Optional[int] = None,
    max_text_chunks_per_table: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Build the documents to embed for a tabular fabric. Returns ``(documents, stats)``."""
    max_entities = max_entities_per_table or settings.FABRIC_MAX_ENTITY_SUMMARIES_PER_TABLE
    max_text = max_text_chunks_per_table or settings.FABRIC_MAX_TEXT_CHUNKS_PER_TABLE
    docs: List[Dict[str, Any]] = []
    stats: Dict[str, Any] = {"dataset_cards": 1, "schema_cards": 0, "entity_summaries": {}, "text_chunks": {}, "warnings": []}

    def _doc(doc_id: str, content: str, chunk_type: str, table: str = "", row_key: str = "", column: str = "") -> Dict[str, Any]:
        meta = {"chunk_type": chunk_type, "pipeline_version": 2}
        if table:
            meta["source_collection"] = table
        if row_key:
            meta["row_key"] = row_key
        if column:
            meta["column"] = column
        return {
            "id": doc_id,
            "content": content,
            "source_name": fabric_name,
            "file_name": table or fabric_name,
            "metadata": meta,
        }

    docs.append(_doc(f"{fabric_id}::dataset", dataset_card(profile, fabric_name), "dataset"))

    for table in profile["tables"]:
        if not table["row_count"]:
            continue
        tname = table["name"]
        docs.append(_doc(f"{fabric_id}::schema::{table['sql_name']}", schema_card(table, profile), "schema", tname))
        stats["schema_cards"] += 1

        text_cols = [c for c in table["columns"] if c["role"] == "text"]
        summarize = table["kind"] == "entity" and bool(table["primary_key"])
        if not summarize and not text_cols:
            continue

        parent_labels = _parent_labels(store, fabric_id, profile, table) if summarize else {}
        child_aggs = _child_aggregates(store, fabric_id, profile, table) if summarize else []
        sql_to_name = {c["sql_name"]: c["name"] for c in table["columns"]}
        entity_count = text_count = 0
        for index, sql_row in enumerate(store.iter_rows(fabric_id, table["sql_name"])):
            row = {sql_to_name[k]: v for k, v in sql_row.items() if k in sql_to_name}
            pk_value = " / ".join(_fmt(row.get(k)) for k in table["primary_key"]) or f"row {index + 1}"
            if summarize and entity_count < max_entities:
                key, text = entity_summary(row, table, parent_labels, child_aggs)
                docs.append(_doc(f"{fabric_id}::entity::{table['sql_name']}::{index}", text, "entity", tname, key))
                entity_count += 1
            elif text_cols and text_count < max_text:
                # Entity summaries already carry the row's long text; other
                # tables get one chunk per long-text value.
                for col in text_cols:
                    value = row.get(col["name"])
                    if not value:
                        continue
                    noun = _singular_label(tname).capitalize()
                    content = f"{noun} {pk_value} — {_humanize(col['name'])}:\n{value}"
                    docs.append(_doc(
                        f"{fabric_id}::text::{table['sql_name']}::{col['sql_name']}::{index}",
                        content, "text", tname, pk_value, col["name"],
                    ))
                    text_count += 1
        if entity_count:
            stats["entity_summaries"][tname] = entity_count
        if text_count:
            stats["text_chunks"][tname] = text_count
        if summarize and table["row_count"] > max_entities:
            stats["warnings"].append(
                f"Table '{tname}': {max_entities:,} of {table['row_count']:,} entity summaries embedded; "
                f"every row is still reachable by id and by SQL."
            )
    stats["documents"] = len(docs)
    return docs, stats
