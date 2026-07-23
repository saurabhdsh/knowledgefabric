"""
Full-fabric deterministic analytics for CSV / database row chunks.

Test with LLM must answer true analytical questions (counts, distributions,
numeric aggregates, unique counts) over **all** indexed rows — never over
preview ``sample_rows`` or a tiny similarity window.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Tuple


ANALYTICAL_TOKENS = (
    "how many",
    "count",
    "number of",
    "total",
    "distribution",
    "breakdown",
    "breakdown by",
    "group by",
    "average",
    "avg",
    "mean",
    "median",
    "minimum",
    "maximum",
    "min ",
    "max ",
    " min",
    " max",
    "sum of",
    "sum(",
    "unique",
    "distinct",
    "percentage",
    "percent",
    "proportion",
    "share of",
    "most common",
    "top ",
    "frequency",
    "histogram",
    "statistics",
    "stats",
    "how much",
)

CATEGORY_HINT_LABELS = (
    "active",
    "inactive",
    "inconclusive",
    "unspecified",
    "probe",
    "true duplicate",
    "near duplicate",
    "not duplicate",
    "corrected claim",
)

PREFERRED_CATEGORICAL_FIELDS = (
    "PUBCHEM_ACTIVITY_OUTCOME",
    "activity_outcome",
    "ACTIVITY_OUTCOME",
    "outcome",
    "duplicate_match_type",
    "match_type",
    "label",
    "status",
    "class",
    "result",
    "decision_route",
)

PREFERRED_NUMERIC_FIELDS = (
    "PUBCHEM_ACTIVITY_SCORE",
    "activity_score",
    "ACTIVITY_SCORE",
    "score",
    "billed_amount",
    "allowed_amount",
    "paid_amount",
    "amount",
    "value",
    "quantity",
    "qty",
)


def parse_row_text(content: str) -> Dict[str, str]:
    """Parse `key: value | key: value` row chunk text into a dict."""
    parsed: Dict[str, str] = {}
    for part in str(content or "").split("|"):
        token = part.strip()
        if ":" not in token:
            continue
        key, value = token.split(":", 1)
        k = key.strip()
        v = value.strip()
        if k:
            parsed[k] = v
    return parsed


def is_analytical_query(query: str) -> bool:
    """True when the question asks for counts, distributions, or aggregates."""
    q = str(query or "").strip().lower()
    if not q:
        return False
    if any(token in q for token in ANALYTICAL_TOKENS):
        return True
    # Implicit categorical distribution: "Active, Inactive, and Inconclusive"
    hits = sum(1 for label in CATEGORY_HINT_LABELS if label in q)
    return hits >= 2


def load_rows_from_source_documents(
    documents: Sequence[Any],
    metadatas: Optional[Sequence[Any]] = None,
) -> List[Dict[str, str]]:
    """Extract row dicts from vector-store document payloads."""
    metadatas = metadatas or []
    rows: List[Dict[str, str]] = []
    for idx, content in enumerate(documents):
        metadata = metadatas[idx] if idx < len(metadatas) and isinstance(metadatas[idx], dict) else {}
        chunk_type = str(metadata.get("chunk_type", "")).strip().lower()
        # Prefer explicit row chunks; if chunk_type missing, still try parseable rows.
        if chunk_type and chunk_type != "row":
            continue
        row = parse_row_text(str(content or ""))
        if row:
            rows.append(row)
    return rows


def _norm_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _columns(rows: Sequence[Dict[str, str]]) -> List[str]:
    seen = set()
    cols: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                cols.append(key)
    return cols


def _find_column(query: str, columns: Sequence[str]) -> Optional[str]:
    """Match a column mentioned in the query (spaces/underscores insensitive)."""
    q = str(query or "").lower()
    q_norm = _norm_key(q)
    best: Optional[Tuple[int, str]] = None
    for col in columns:
        variants = {
            col.lower(),
            col.lower().replace("_", " "),
            col.lower().replace("_", ""),
            _norm_key(col),
        }
        for variant in variants:
            if not variant or len(variant) < 3:
                continue
            if variant in q or _norm_key(variant) in q_norm:
                score = len(_norm_key(variant))
                if best is None or score > best[0]:
                    best = (score, col)
    return best[1] if best else None


def _pick_categorical_field(rows: Sequence[Dict[str, str]], query: str) -> Optional[str]:
    columns = _columns(rows)
    mentioned = _find_column(query, columns)
    if mentioned:
        return mentioned
    lower_map = {_norm_key(c): c for c in columns}
    for preferred in PREFERRED_CATEGORICAL_FIELDS:
        hit = lower_map.get(_norm_key(preferred))
        if hit:
            return hit
    # Heuristic: low-cardinality string-like columns
    sample = rows[: min(200, len(rows))]
    best_col = None
    best_score = -1.0
    for col in columns:
        values = [str(r.get(col, "")).strip() for r in sample if str(r.get(col, "")).strip()]
        if len(values) < max(3, len(sample) // 5):
            continue
        # Skip mostly-numeric columns for categorical default
        numeric_hits = sum(1 for v in values if _to_float(v) is not None)
        if numeric_hits / max(1, len(values)) > 0.8:
            continue
        uniq = len(set(v.lower() for v in values))
        if uniq < 2 or uniq > min(50, max(5, len(values) // 2)):
            continue
        score = (len(values) / max(1, len(sample))) - (uniq / 100.0)
        if score > best_score:
            best_score = score
            best_col = col
    return best_col


def _pick_numeric_field(rows: Sequence[Dict[str, str]], query: str) -> Optional[str]:
    columns = _columns(rows)
    mentioned = _find_column(query, columns)
    if mentioned and _column_is_mostly_numeric(rows, mentioned):
        return mentioned
    lower_map = {_norm_key(c): c for c in columns}
    for preferred in PREFERRED_NUMERIC_FIELDS:
        hit = lower_map.get(_norm_key(preferred))
        if hit and _column_is_mostly_numeric(rows, hit):
            return hit
    # Any mostly-numeric column whose name suggests a measure
    for col in columns:
        kl = col.lower()
        if any(tok in kl for tok in ("score", "amount", "value", "qty", "quantity", "rate", "percent")):
            if _column_is_mostly_numeric(rows, col):
                return col
    for col in columns:
        if _column_is_mostly_numeric(rows, col):
            return col
    return None


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {"none", "nan", "null", "na", "n/a"}:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _column_is_mostly_numeric(rows: Sequence[Dict[str, str]], column: str) -> bool:
    values = [str(r.get(column, "")).strip() for r in rows[:200] if str(r.get(column, "")).strip()]
    if not values:
        return False
    hits = sum(1 for v in values if _to_float(v) is not None)
    return (hits / len(values)) >= 0.6


def _extract_target_labels(query: str) -> List[str]:
    text = str(query or "")
    known = (
        "Active",
        "Inactive",
        "Inconclusive",
        "Unspecified",
        "Probe",
        "True Duplicate",
        "Near Duplicate",
        "Not Duplicate",
        "Corrected Claim",
    )
    found: List[str] = []
    lower = text.lower()
    for label in known:
        if label.lower() in lower:
            found.append(label)
    return found


def _wants_total_only(query: str, columns: Sequence[str]) -> bool:
    q = str(query or "").strip().lower()
    if not any(tok in q for tok in ("how many", "count", "number of", "total")):
        return False
    # If user named categories or a field, not a bare total.
    if _extract_target_labels(query):
        return False
    if _find_column(query, columns):
        # "how many unique CID" / "count of activity score" handled elsewhere
        if any(tok in q for tok in ("unique", "distinct", "average", "avg", "mean", "median", "min", "max", "sum")):
            return False
        # "how many Active" already caught by labels; field-only count → distribution
        return False
    entity_tokens = (
        "compound",
        "compounds",
        "row",
        "rows",
        "record",
        "records",
        "entry",
        "entries",
        "item",
        "items",
        "claim",
        "claims",
        "total",
    )
    return any(tok in q for tok in entity_tokens) or q.strip() in {
        "count",
        "total",
        "how many",
        "number of rows",
        "total rows",
        "row count",
    }


def _wants_unique(query: str) -> bool:
    q = str(query or "").lower()
    return "unique" in q or "distinct" in q


def _wants_numeric_agg(query: str) -> Optional[str]:
    q = str(query or "").lower()
    if any(tok in q for tok in ("average", "avg", "mean")):
        return "average"
    if "median" in q:
        return "median"
    if "sum of" in q or "sum(" in q or re.search(r"\bsum\b", q):
        return "sum"
    if "minimum" in q or re.search(r"\bmin\b", q):
        return "min"
    if "maximum" in q or re.search(r"\bmax\b", q):
        return "max"
    return None


def _value_counts(rows: Sequence[Dict[str, str]], field: str) -> Dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        value = str(row.get(field, "")).strip()
        if value:
            counter[value] += 1
    return dict(counter.most_common())


def _order_counts(counts: Dict[str, int], target_labels: Sequence[str]) -> Dict[str, int]:
    if not target_labels:
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower())))
    target_norm = {str(t).strip().lower(): str(t).strip() for t in target_labels if str(t).strip()}
    by_lower = {k.lower(): (k, v) for k, v in counts.items()}
    ordered: Dict[str, int] = {}
    for want_lower, want_display in target_norm.items():
        if want_lower in by_lower:
            real_key, real_val = by_lower[want_lower]
            ordered[real_key] = real_val
        else:
            ordered[want_display] = 0
    for key, val in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower())):
        if key.lower() not in target_norm:
            ordered[key] = val
    return ordered


def _numeric_stats(rows: Sequence[Dict[str, str]], field: str) -> Optional[Dict[str, float]]:
    numbers: List[float] = []
    for row in rows:
        number = _to_float(row.get(field))
        if number is not None:
            numbers.append(number)
    if not numbers:
        return None
    numbers.sort()
    n = len(numbers)
    mid = n // 2
    if n % 2:
        median = numbers[mid]
    else:
        median = (numbers[mid - 1] + numbers[mid]) / 2.0
    return {
        "count": float(n),
        "sum": float(sum(numbers)),
        "average": float(sum(numbers) / n),
        "median": float(median),
        "min": float(numbers[0]),
        "max": float(numbers[-1]),
    }


def _fmt_number(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.6g}"


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """Build a GitHub-flavored markdown table."""
    header_cells = [str(h) for h in headers]
    lines = [
        "| " + " | ".join(header_cells) + " |",
        "| " + " | ".join(["---"] * len(header_cells)) + " |",
    ]
    for row in rows:
        cells = [str(c) if c is not None else "" for c in row]
        # Pad/truncate to header width
        while len(cells) < len(header_cells):
            cells.append("")
        cells = cells[: len(header_cells)]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# Back-compat aliases
_markdown_table = markdown_table


def format_total_rows_answer(fabric_name: str, row_total: int, *, note: str = "") -> str:
    parts = [
        f"## Summary",
        f"Full-fabric row count for **{fabric_name}**.",
        "",
        _markdown_table(["Metric", "Value"], [["Total rows / compounds", row_total]]),
        "",
        "### Notes",
        "- Computed over **all indexed row chunks**, not preview `sample_rows`.",
    ]
    if note:
        parts.append(f"- {note}")
    return "\n".join(parts)


def format_unique_count_answer(
    fabric_name: str,
    field: str,
    distinct: int,
    row_total: int,
) -> str:
    return "\n".join(
        [
            "## Summary",
            f"Distinct values of `{field}` in **{fabric_name}**.",
            "",
            _markdown_table(
                ["Metric", "Value"],
                [
                    [f"Distinct `{field}`", distinct],
                    ["Rows scanned", row_total],
                ],
            ),
            "",
            "### Notes",
            "- Computed over **all indexed row chunks**, not preview `sample_rows`.",
        ]
    )


def format_numeric_answer(
    fabric_name: str,
    field: str,
    stats: Dict[str, float],
    *,
    highlight: Optional[str] = None,
    title: str = "Numeric summary",
) -> str:
    rows = [
        ["Count (numeric)", int(stats["count"])],
        ["Min", _fmt_number(stats["min"])],
        ["Max", _fmt_number(stats["max"])],
        ["Average", _fmt_number(stats["average"])],
        ["Median", _fmt_number(stats["median"])],
        ["Sum", _fmt_number(stats["sum"])],
    ]
    highlight_line = ""
    if highlight and highlight in stats:
        highlight_line = (
            f"\n**Highlighted:** {highlight} of `{field}` = "
            f"**{_fmt_number(stats[highlight])}**\n"
        )
    return "\n".join(
        [
            f"## {title}",
            f"Analytics for `{field}` in **{fabric_name}**.",
            highlight_line.rstrip(),
            "",
            _markdown_table(["Statistic", "Value"], rows),
            "",
            "### Notes",
            "- Computed over **all indexed row chunks**, not preview `sample_rows`.",
        ]
    )


def format_value_counts_answer(
    fabric_name: str,
    field: str,
    counts: Dict[str, int],
    *,
    include_pct: bool = True,
) -> str:
    counted = sum(counts.values())
    table_rows: List[List[Any]] = []
    for label, value in counts.items():
        if include_pct and counted:
            pct = 100.0 * float(value) / float(counted)
            table_rows.append([label, value, f"{pct:.2f}%"])
        else:
            table_rows.append([label, value])
    headers = ["Category", "Count", "Percentage"] if include_pct else ["Category", "Count"]
    if include_pct:
        table_rows.append(["**Total**", counted, "100.00%"])
    else:
        table_rows.append(["**Total**", counted])
    return "\n".join(
        [
            "## Summary",
            f"Distribution of `{field}` in **{fabric_name}** (full indexed fabric).",
            "",
            _markdown_table(headers, table_rows),
            "",
            "### Notes",
            "- Totals are computed over **all indexed row chunks**, not preview `sample_rows`.",
        ]
    )


def analyze_tabular_query(
    rows: Sequence[Dict[str, str]],
    query: str,
    *,
    fabric_name: str = "knowledge fabric",
) -> Optional[Dict[str, Any]]:
    """
    Run deterministic analytics over all provided rows.

    Returns a dict with ``answer``, ``intent``, ``row_total``, and metrics,
    or ``None`` if the query is not analytical / cannot be answered from rows.
    Answers are markdown (headings + tables) for Test with LLM rendering.
    """
    if not rows or not is_analytical_query(query):
        return None

    columns = _columns(rows)
    row_total = len(rows)
    labels = _extract_target_labels(query)
    unique_intent = _wants_unique(query)
    numeric_intent = _wants_numeric_agg(query)
    q_lower = str(query).lower()
    include_pct = any(tok in q_lower for tok in ("percent", "percentage", "proportion", "share"))
    # Distributions always get a percentage column for readability.
    force_pct_column = True

    # 1) Bare total row/compound count
    if _wants_total_only(query, columns) and not unique_intent and not numeric_intent and not labels:
        return {
            "intent": "total_rows",
            "row_total": row_total,
            "answer": format_total_rows_answer(fabric_name, row_total),
            "metrics": {"row_total": row_total},
        }

    # 2) Unique / distinct count
    if unique_intent:
        field = _find_column(query, columns) or _pick_categorical_field(rows, query)
        if not field:
            return None
        values = {str(r.get(field, "")).strip() for r in rows if str(r.get(field, "")).strip()}
        return {
            "intent": "unique_count",
            "row_total": row_total,
            "field": field,
            "answer": format_unique_count_answer(fabric_name, field, len(values), row_total),
            "metrics": {"field": field, "distinct": len(values), "row_total": row_total},
        }

    # 3) Numeric aggregates
    if numeric_intent:
        field = _pick_numeric_field(rows, query)
        if not field:
            return None
        stats = _numeric_stats(rows, field)
        if not stats:
            return None
        key = numeric_intent
        return {
            "intent": f"numeric_{key}",
            "row_total": row_total,
            "field": field,
            "answer": format_numeric_answer(
                fabric_name,
                field,
                stats,
                highlight=key,
                title=f"{key.capitalize()} of `{field}`",
            ),
            "metrics": {"field": field, **stats},
        }

    # 4) Categorical distribution / labeled counts / breakdown
    field = _pick_categorical_field(rows, query)
    if field and _column_is_mostly_numeric(rows, field):
        # "distribution of activity score" → numeric summary, not thousands of buckets
        uniq_estimate = len({str(r.get(field, "")).strip() for r in rows[:500] if str(r.get(field, "")).strip()})
        if uniq_estimate > 40 or not labels:
            stats = _numeric_stats(rows, field)
            if stats:
                return {
                    "intent": "numeric_summary",
                    "row_total": row_total,
                    "field": field,
                    "answer": format_numeric_answer(
                        fabric_name,
                        field,
                        stats,
                        title=f"Numeric summary of `{field}`",
                    ),
                    "metrics": {"field": field, **stats},
                }

    if not field:
        # Fall back to total if we only asked for a count and have rows.
        if any(tok in q_lower for tok in ("how many", "count", "total", "number of")):
            return {
                "intent": "total_rows",
                "row_total": row_total,
                "answer": format_total_rows_answer(
                    fabric_name,
                    row_total,
                    note="No categorical field could be inferred for a breakdown.",
                ),
                "metrics": {"row_total": row_total},
            }
        return None

    counts = _order_counts(_value_counts(rows, field), labels)
    counted = sum(counts.values())
    return {
        "intent": "value_counts",
        "row_total": counted,
        "field": field,
        "answer": format_value_counts_answer(
            fabric_name,
            field,
            counts,
            include_pct=force_pct_column or include_pct,
        ),
        "metrics": {"field": field, "counts": counts, "row_total": counted},
    }


def analyze_source_documents(
    documents: Sequence[Any],
    query: str,
    *,
    metadatas: Optional[Sequence[Any]] = None,
    fabric_name: str = "knowledge fabric",
) -> Optional[Dict[str, Any]]:
    """Convenience: parse source documents then analyze."""
    rows = load_rows_from_source_documents(documents, metadatas)
    result = analyze_tabular_query(rows, query, fabric_name=fabric_name)
    if result is not None:
        result["indexed_documents"] = len(documents)
        result["parsed_rows"] = len(rows)
    return result
