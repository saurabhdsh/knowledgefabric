"""Profile tabular data before a fabric is built (Release 2.0, Phase 1).

For every table: column types, null rates, distinct counts, key candidates and
a primary key. Across tables: foreign keys found by value inclusion (how many
of a column's distinct values exist in another table's key), not by column
name alone. The profile drives the table store, the index and the ontology.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from itertools import combinations
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.core.config import settings

NULL_STRINGS = {"", "null", "none", "nan", "nat"}

_INT_RE = re.compile(r"^[+-]?(0|[1-9]\d{0,17})$")
_FLOAT_RE = re.compile(r"^[+-]?((0|[1-9]\d*)(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")
_DIGITS_RE = re.compile(r"^[+-]?\d+$")
_MONEY_RE = re.compile(r"^-?\$?\d{1,3}(,\d{3})+(\.\d+)?$|^-?\$\d+(\.\d+)?$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d{1,9})?)?(Z|[+-]\d{2}:?\d{2})?$"
)
_SLASH_DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_BOOL_TRUE = {"true"}
_BOOL_FALSE = {"false"}

_ID_SUFFIXES = ("_id", "_key", "_code", "_number", "_no", "_num", "_uuid", "_guid")
_ID_NAMES = {"id", "uuid", "guid", "key", "code"}
_CAMEL_ID_RE = re.compile(r"[a-z0-9](ID|Id|Key|Code|Number)$")
_LABEL_NAME_RE = re.compile(r"(^name$|_name$|^title$|_title$|^label$|_label$)", re.I)
_MONEY_NAME_RE = re.compile(
    r"(amount|cost|paid|billed|charge|price|revenue|total|balance|payment|fee|spend|impact)", re.I
)

MAX_SAMPLE_VALUES = 8
TEXT_MIN_AVG_LENGTH = 60
CATEGORY_MAX_DISTINCT = 50


def is_id_name(name: str) -> bool:
    """Whether a column name reads like an identifier (member_id, memberId, code)."""
    lowered = name.lower()
    return lowered in _ID_NAMES or lowered.endswith(_ID_SUFFIXES) or bool(_CAMEL_ID_RE.search(name))


def is_null(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip().lower() in NULL_STRINGS:
        return True
    return False


def _singular(name: str) -> str:
    n = name.lower()
    if n.endswith("ies") and len(n) > 4:
        return n[:-3] + "y"
    if n.endswith("ses") and len(n) > 4:
        return n[:-2]
    if n.endswith("s") and not n.endswith("ss") and len(n) > 3:
        return n[:-1]
    return n


def _slash_order(values: Sequence[str]) -> Optional[str]:
    """'mdy', 'dmy', or None when the values are not all slash dates."""
    first_gt_12 = second_gt_12 = False
    for v in values:
        m = _SLASH_DATE_RE.match(v)
        if not m:
            return None
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12:
            first_gt_12 = True
        if b > 12:
            second_gt_12 = True
        if a > 31 or b > 31 or (a > 12 and b > 12):
            return None
    if first_gt_12 and not second_gt_12:
        return "dmy"
    return "mdy"


def infer_column_type(values: Sequence[Any]) -> Tuple[str, Dict[str, Any]]:
    """Type of a column from its non-null values.

    Strict: a column is numeric / boolean / date only when every non-null value
    parses as such; otherwise it is a string. Returns ``(type, details)`` where
    type is integer | float | boolean | date | datetime | string | json.
    """
    details: Dict[str, Any] = {}
    if not values:
        return "string", {"empty": True}

    native = Counter(type(v).__name__ for v in values)
    if all(isinstance(v, bool) for v in values):
        return "boolean", details
    if all(isinstance(v, int) and not isinstance(v, bool) for v in values):
        return "integer", details
    if all(isinstance(v, (int, float, Decimal)) and not isinstance(v, bool) for v in values):
        return "float", details
    if all(isinstance(v, datetime) for v in values):
        return "datetime", details
    if all(isinstance(v, date) for v in values):
        return "date", details
    if any(isinstance(v, (dict, list, tuple, set)) for v in values):
        return "json", details
    if not all(isinstance(v, str) for v in values):
        # Mixed native types (e.g. ints and strings): keep as text, say so.
        details["mixed_native_types"] = dict(native)

    strs = [str(v).strip() for v in values]
    if all(_INT_RE.match(s) for s in strs):
        return "integer", details
    # Digit strings with a leading zero or more than 18 digits (NDC codes, card
    # numbers) are identifiers: keep them as text so no digit is lost.
    if all(_FLOAT_RE.match(s) for s in strs) and not any(
        _DIGITS_RE.match(s) and not _INT_RE.match(s) for s in strs
    ):
        return "float", details
    lowered = {s.lower() for s in strs}
    if lowered <= (_BOOL_TRUE | _BOOL_FALSE):
        return "boolean", details
    if all(_ISO_DATE_RE.match(s) for s in strs):
        return "date", details
    if all(_ISO_DATETIME_RE.match(s) or _ISO_DATE_RE.match(s) for s in strs):
        return "datetime", details
    order = _slash_order(strs)
    if order:
        details["date_format"] = "DD/MM/YYYY" if order == "dmy" else "MM/DD/YYYY"
        ambiguous = all(
            int(_SLASH_DATE_RE.match(s).group(1)) <= 12 and int(_SLASH_DATE_RE.match(s).group(2)) <= 12
            for s in strs
        )
        if ambiguous:
            details["date_format_ambiguous"] = True
        return "date", details
    if all(_MONEY_RE.match(s) for s in strs):
        details["parsed_from"] = "currency"
        return "float", details
    return "string", details


def normalize_value(value: Any, col_type: str, details: Optional[Dict[str, Any]] = None) -> Any:
    """Convert one raw value to what the table store holds for ``col_type``."""
    if is_null(value):
        return None
    details = details or {}
    try:
        if col_type == "integer":
            return int(value) if not isinstance(value, str) else int(value.strip())
        if col_type == "float":
            if isinstance(value, str):
                cleaned = value.strip()
                if details.get("parsed_from") == "currency":
                    cleaned = cleaned.replace("$", "").replace(",", "")
                return float(cleaned)
            return float(value)
        if col_type == "boolean":
            if isinstance(value, bool):
                return 1 if value else 0
            return 1 if str(value).strip().lower() in _BOOL_TRUE else 0
        if col_type == "date":
            if isinstance(value, datetime):
                return value.date().isoformat()
            if isinstance(value, date):
                return value.isoformat()
            s = str(value).strip()
            m = _SLASH_DATE_RE.match(s)
            if m:
                a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                month, day = (b, a) if details.get("date_format") == "DD/MM/YYYY" else (a, b)
                return f"{y:04d}-{month:02d}-{day:02d}"
            return s
        if col_type == "datetime":
            if isinstance(value, (datetime, date)):
                return value.isoformat()
            return str(value).strip().replace("T", " ")
        if col_type == "json":
            import json

            if isinstance(value, (dict, list, tuple, set)):
                return json.dumps(list(value) if isinstance(value, (set, tuple)) else value, default=str)
            return str(value)
    except (TypeError, ValueError):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _hashable(value: Any) -> Any:
    try:
        hash(value)
        return value
    except TypeError:
        return str(value)


def _profile_column(name: str, raw_values: List[Any], row_count: int) -> Dict[str, Any]:
    non_null = [v for v in raw_values if not is_null(v)]
    col_type, details = infer_column_type(non_null)
    normalized = [normalize_value(v, col_type, details) for v in non_null]
    counts = Counter(_hashable(v) for v in normalized)
    distinct = len(counts)
    null_count = row_count - len(non_null)

    column: Dict[str, Any] = {
        "name": name,
        "type": col_type,
        "null_count": null_count,
        "null_rate": round(null_count / row_count, 4) if row_count else 0.0,
        "distinct_count": distinct,
        "distinct_ratio": round(distinct / len(non_null), 4) if non_null else 0.0,
        "is_unique": bool(non_null) and distinct == len(non_null),
        "sample_values": [v for v, _ in counts.most_common(MAX_SAMPLE_VALUES)],
    }
    column.update(details)

    if col_type in ("integer", "float") and normalized:
        nums = [float(v) for v in normalized]
        column["min"] = min(nums)
        column["max"] = max(nums)
        column["mean"] = round(sum(nums) / len(nums), 4)
    elif col_type in ("date", "datetime") and normalized:
        column["min"] = min(normalized)
        column["max"] = max(normalized)
    elif col_type == "string" and normalized:
        lengths = [len(str(v)) for v in normalized]
        column["avg_length"] = round(sum(lengths) / len(lengths), 1)
        column["max_length"] = max(lengths)
    # Kept only for FK discovery; removed from the profile before it is returned.
    column["_distinct"] = set(counts.keys())
    return column


def _column_role(column: Dict[str, Any], row_count: int) -> str:
    t = column["type"]
    name = column["name"]
    if t == "boolean":
        return "flag"
    if t in ("date", "datetime"):
        return "date"
    if t == "json":
        return "nested"
    if t in ("integer", "float"):
        if t == "integer" and (is_id_name(name) or (column["is_unique"] and row_count >= 20)):
            return "identifier"
        return "measure"
    if is_id_name(name):
        return "identifier"
    if column.get("avg_length", 0) >= TEXT_MIN_AVG_LENGTH:
        return "text"
    if _LABEL_NAME_RE.search(name):
        return "label"
    distinct = column["distinct_count"]
    if distinct <= CATEGORY_MAX_DISTINCT and (row_count < 20 or distinct <= max(2, row_count * 0.5)):
        return "category"
    return "attribute"


def _key_score(table_name: str, column: Dict[str, Any], position: int) -> float:
    name = column["name"].lower()
    singular = _singular(table_name)
    score = 0.0
    if name == "id" or name in (f"{singular}_id", f"{table_name.lower()}_id", f"{singular}id"):
        score += 3.0
    elif is_id_name(name):
        score += 2.0
    if singular and singular in name:
        score += 0.5
    if column["type"] in ("integer", "string"):
        score += 0.5
    score += max(0.0, 0.5 - 0.05 * position)
    return score


def _is_key_candidate(column: Dict[str, Any], row_count: int) -> bool:
    if not column["is_unique"] or column["null_count"] > 0:
        return False
    # In a tiny table every column is unique; only trust identifier-like names there.
    if row_count < 20 and not is_id_name(column["name"]):
        return False
    if column["type"] not in ("integer", "string"):
        return False
    if column["type"] == "string" and column.get("avg_length", 0) > 64:
        return False
    return True


def _profile_table(name: str, rows: List[Dict[str, Any]], source_row_count: Optional[int] = None) -> Dict[str, Any]:
    """Profile one table. Keys starting with ``__`` are ingestion metadata and skipped."""
    column_names: List[str] = []
    seen = set()
    for row in rows:
        for key in row.keys():
            k = str(key)
            if k.startswith("__") or k in seen:
                continue
            seen.add(k)
            column_names.append(k)

    row_count = len(rows)
    columns = [
        _profile_column(col, [row.get(col) for row in rows], row_count)
        for col in column_names
    ]
    for col in columns:
        col["role"] = _column_role(col, row_count)

    candidates = [c for c in columns if _is_key_candidate(c, row_count)] if row_count else []
    ranked = sorted(
        candidates,
        key=lambda c: _key_score(name, c, column_names.index(c["name"])),
        reverse=True,
    )
    primary_key: List[str] = []
    if ranked:
        primary_key = [ranked[0]["name"]]
    if not primary_key and row_count:
        id_like = [
            c["name"] for c in columns
            if c["null_count"] == 0 and c["type"] in ("integer", "string") and is_id_name(c["name"])
        ][:6]
        for a, b in combinations(id_like, 2):
            pairs = {(_hashable(r.get(a)), _hashable(r.get(b))) for r in rows}
            if len(pairs) == row_count:
                primary_key = [a, b]
                break

    # Pairs of identifier columns that identify a row together while neither
    # does alone, e.g. (order_id, line_no). Another table can point at such a pair.
    composite_keys: List[List[str]] = []
    if len(primary_key) == 2:
        composite_keys.append(list(primary_key))
    if row_count:
        pair_cols = [
            c["name"] for c in columns
            if c["null_count"] == 0 and c["type"] in ("integer", "string")
            and is_id_name(c["name"]) and not c["is_unique"]
        ][:6]
        for a, b in combinations(pair_cols, 2):
            if [a, b] in composite_keys:
                continue
            pairs = {(_hashable(r.get(a)), _hashable(r.get(b))) for r in rows}
            if len(pairs) == row_count:
                composite_keys.append([a, b])

    for col in columns:
        if col["name"] in primary_key:
            col["role"] = "identifier"

    label_column = next(
        (c["name"] for c in columns if c["type"] == "string" and _LABEL_NAME_RE.search(c["name"])
         and c["name"] not in primary_key),
        None,
    )

    is_sample = source_row_count is not None and source_row_count > row_count
    return {
        "name": name,
        "row_count": row_count,
        "source_row_count": source_row_count,
        "is_sample": bool(is_sample),
        "columns": columns,
        "primary_key": primary_key,
        "key_candidates": [c["name"] for c in ranked],
        "composite_key_candidates": composite_keys,
        "label_column": label_column,
    }


def _name_affinity(child_col: str, parent_table: str, parent_col: str) -> float:
    """0..1: how strongly the child column's name points at the parent key."""
    c, p = child_col.lower(), parent_col.lower()
    singular = _singular(parent_table)
    if c == p and p != "id":
        return 1.0
    if p != "id" and c.endswith(p):
        return 0.9  # pcp_provider_id -> provider_id
    if singular and (c == f"{singular}_id" or c == f"{singular}id" or c == singular):
        return 0.9
    if singular and len(singular) >= 3 and singular in c:
        return 0.7
    return 0.0


# A link below the acceptance threshold is not thrown away when there is a
# reason to look at it: it is listed for review with the reason, and it is not
# used for joins, the graph, or the ontology until someone accepts it.
REVIEW_MIN_OVERLAP = 0.5
# Without a name that points at the parent, this many distinct values must agree.
MIN_SUPPORT_WITHOUT_NAME = 10
LOW_SUPPORT = 5
MIN_ACCEPT_CONFIDENCE = 0.5


def wilson_lower(successes: int, n: int, z: float = 1.96) -> float:
    """Lower end of the 95% Wilson interval for ``successes`` out of ``n``.

    Two matches out of two is weak evidence (0.34); forty out of forty is
    strong (0.91). This is what keeps a tiny column from scoring 1.0.
    """
    if n <= 0:
        return 0.0
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / denom)


def _link_confidence(matched: int, n: int, affinity: float, id_like: bool) -> Tuple[float, float]:
    """``(confidence, value_confidence)`` for a candidate link.

    ``value_confidence`` is what the values alone support. A name that points
    at the parent key is independent evidence, so it is averaged in; with no
    such name the values have to carry the link on their own, discounted.
    """
    value_conf = wilson_lower(matched, n)
    if affinity > 0:
        confidence = max(value_conf, (value_conf + affinity) / 2)
    else:
        confidence = value_conf * (0.7 if id_like else 0.6)
    return round(confidence, 4), round(value_conf, 4)


def _sample_note(table: Dict[str, Any]) -> str:
    return (
        f"'{table['name']}' is a sample of {table['row_count']:,} of {table['source_row_count']:,} source rows, "
        "so values with no match may be in rows that were not imported"
    )


def discover_foreign_keys(
    tables: List[Dict[str, Any]],
    min_overlap: Optional[float] = None,
    review_out: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Find foreign keys by inclusion: child values contained in a parent key.

    ``overlap`` is the share of the child column's distinct values that exist in
    the parent key. Name affinity is used only to rank and to keep small-integer
    columns (ages, counts) from matching surrogate keys by accident.

    Returns the accepted links. Links that are plausible but not proven are
    appended to ``review_out`` with ``status: needs_review`` and the reasons:
    too many values without a parent row, a parent table that is only a
    sample, or too few values to tell.
    """
    threshold = settings.FABRIC_FK_MIN_OVERLAP if min_overlap is None else min_overlap
    parents: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for table in tables:
        cols = {c["name"]: c for c in table["columns"]}
        for key_name in table["key_candidates"]:
            parents.append((table, cols[key_name]))

    best: Dict[Tuple[str, str], Dict[str, Any]] = {}
    best_review: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for child in tables:
        for col in child["columns"]:
            if col["type"] not in ("integer", "string") or col["distinct_count"] == 0:
                continue
            if col["role"] in ("text", "flag", "date", "nested"):
                continue
            child_values = col["_distinct"]
            n = len(child_values)
            for parent, pkey in parents:
                same_table = parent["name"] == child["name"]
                if same_table and pkey["name"] == col["name"]:
                    continue
                if pkey["type"] != col["type"]:
                    continue
                matched = len(child_values & pkey["_distinct"])
                if not matched:
                    continue
                overlap = matched / n
                affinity = _name_affinity(col["name"], parent["name"], pkey["name"])
                id_like = is_id_name(col["name"])
                if same_table and affinity < 0.9 and not id_like:
                    continue
                # Integers with no naming evidence (ages, counts) are never trusted.
                if affinity == 0 and col["type"] != "string":
                    continue
                # A column that is itself a key of its table and matches another
                # table's key 1:1 is a shared key; keep it only with naming evidence.
                if col["name"] in child["key_candidates"] and affinity == 0:
                    continue
                confidence, value_conf = _link_confidence(matched, n, affinity, id_like)
                parent_sampled = bool(parent.get("is_sample")) and bool(parent.get("source_row_count"))
                reasons: List[str] = []
                status = "accepted"
                if overlap < threshold:
                    if parent_sampled and affinity > 0:
                        fraction = parent["row_count"] / max(1, parent["source_row_count"])
                        if overlap < max(0.1, 0.8 * fraction):
                            continue
                        reasons.append(
                            f"{n - matched} of {n} distinct values have no parent row, and "
                            + _sample_note(parent)
                        )
                    elif overlap >= REVIEW_MIN_OVERLAP and (affinity > 0 or id_like):
                        reasons.append(
                            f"{n - matched} of {n} distinct values ({1 - overlap:.0%}) have no matching parent row"
                        )
                    else:
                        continue
                    status = "needs_review"
                elif affinity == 0 and n < MIN_SUPPORT_WITHOUT_NAME:
                    status = "needs_review"
                    reasons.append(
                        f"only {n} distinct value(s) and the column name does not point at "
                        f"{parent['name']}.{pkey['name']}"
                    )
                elif confidence < MIN_ACCEPT_CONFIDENCE:
                    status = "needs_review"
                    reasons.append(f"only {n} distinct value(s) support this link")
                if status == "accepted" and parent_sampled:
                    reasons.append(_sample_note(parent))
                is_pk = [pkey["name"]] == parent["primary_key"]
                if affinity > 0:
                    basis = (
                        f"{matched} of {n} distinct values exist in {parent['name']}.{pkey['name']}, "
                        "and the column name points at that key"
                    )
                else:
                    basis = (
                        f"{matched} of {n} distinct values exist in {parent['name']}.{pkey['name']}; "
                        "the column names do not agree, so the values alone support this link"
                    )
                candidate = {
                    "from_table": child["name"],
                    "from_column": col["name"],
                    "to_table": parent["name"],
                    "to_column": pkey["name"],
                    "overlap": round(overlap, 4),
                    "confidence": confidence,
                    "value_confidence": value_conf,
                    "name_affinity": affinity,
                    "matched_values": matched,
                    "distinct_values": n,
                    "orphan_values": n - matched,
                    "parent_coverage": round(matched / max(1, pkey["distinct_count"]), 4),
                    "cardinality": "one-to-one" if col["is_unique"] else "many-to-one",
                    "evidence": "value-inclusion" + ("+name" if affinity > 0 else ""),
                    "status": status,
                    "support": "low" if n < LOW_SUPPORT else "ok",
                    "parent_is_sample": parent_sampled,
                    "confidence_basis": basis,
                    "review_reasons": reasons,
                    "_rank": (
                        confidence,
                        affinity,
                        1 if is_pk else 0,
                        1 if _singular(parent["name"]) in col["name"].lower() else 0,
                        parent["row_count"],
                    ),
                }
                key = (child["name"], col["name"])
                bucket = best if status == "accepted" else best_review
                if key not in bucket or candidate["_rank"] > bucket[key]["_rank"]:
                    bucket[key] = candidate

    fks = sorted(best.values(), key=lambda f: (f["from_table"], f["from_column"]))
    for fk in fks:
        fk.pop("_rank", None)
    if review_out is not None:
        for key in sorted(best_review):
            if key in best:
                continue  # the column already has an accepted parent
            cand = best_review[key]
            cand.pop("_rank", None)
            review_out.append(cand)
    return fks


def discover_composite_foreign_keys(
    tables: List[Dict[str, Any]],
    raw_tables: Dict[str, List[Dict[str, Any]]],
    min_overlap: Optional[float] = None,
    review_out: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Two-column foreign keys: a pair of child columns contained in a two-column key.

    A table such as order lines is identified by (order_id, line_no). A child
    that carries the same pair points at one line, which no single column can
    express. Must run while the per-column ``_distinct`` sets are still present.
    """
    threshold = settings.FABRIC_FK_MIN_OVERLAP if min_overlap is None else min_overlap
    found: List[Dict[str, Any]] = []
    pending: List[Dict[str, Any]] = []

    def _tuples(table: Dict[str, Any], names: Sequence[str]) -> set:
        cols = {c["name"]: c for c in table["columns"]}
        out = set()
        for row in raw_tables.get(table["name"], []):
            values = []
            for name in names:
                raw = row.get(name)
                if is_null(raw):
                    break
                values.append(_hashable(normalize_value(raw, cols[name]["type"], cols[name])))
            else:
                out.add(tuple(values))
        return out

    parent_keys = [
        (parent, list(pk))
        for parent in tables if parent["row_count"]
        for pk in (parent.get("composite_key_candidates") or [])
    ]
    seen_links: set = set()
    for parent, pk in parent_keys:
        pcols = {c["name"]: c for c in parent["columns"]}
        parent_tuples = _tuples(parent, pk)
        for child in tables:
            if child["name"] == parent["name"] or not child["row_count"]:
                continue
            options: List[List[Tuple[Dict[str, Any], float]]] = []
            for key_name in pk:
                key_col = pcols[key_name]
                matches: List[Tuple[Dict[str, Any], float]] = []
                for col in child["columns"]:
                    if col["type"] != key_col["type"] or not col["distinct_count"]:
                        continue
                    if col["role"] in ("text", "flag", "date", "nested"):
                        continue
                    shared = len(col["_distinct"] & key_col["_distinct"])
                    if shared / len(col["_distinct"]) < REVIEW_MIN_OVERLAP:
                        continue
                    matches.append((col, _name_affinity(col["name"], parent["name"], key_name)))
                matches.sort(key=lambda m: -m[1])
                options.append(matches[:3])
            if len(options) != 2 or not options[0] or not options[1]:
                continue
            best_pair: Optional[Dict[str, Any]] = None
            for a, aff_a in options[0]:
                for b, aff_b in options[1]:
                    if a["name"] == b["name"]:
                        continue
                    child_tuples = _tuples(child, (a["name"], b["name"]))
                    if not child_tuples:
                        continue
                    n = len(child_tuples)
                    matched = len(child_tuples & parent_tuples)
                    overlap = matched / n
                    if overlap < REVIEW_MIN_OVERLAP:
                        continue
                    affinity = min(aff_a, aff_b)
                    confidence, value_conf = _link_confidence(matched, n, affinity, True)
                    reasons: List[str] = []
                    status = "accepted"
                    if overlap < threshold:
                        status = "needs_review"
                        reasons.append(f"{n - matched} of {n} distinct pairs have no matching parent row")
                    elif affinity == 0:
                        status = "needs_review"
                        reasons.append("the column names do not point at the parent key")
                    elif confidence < MIN_ACCEPT_CONFIDENCE:
                        status = "needs_review"
                        reasons.append(f"only {n} distinct pair(s) support this link")
                    candidate = {
                        "from_table": child["name"],
                        "from_columns": [a["name"], b["name"]],
                        "to_table": parent["name"],
                        "to_columns": list(pk),
                        "overlap": round(overlap, 4),
                        "confidence": confidence,
                        "value_confidence": value_conf,
                        "name_affinity": affinity,
                        "matched_values": matched,
                        "distinct_values": n,
                        "orphan_values": n - matched,
                        "cardinality": "one-to-one" if n == child["row_count"] else "many-to-one",
                        "evidence": "pair-inclusion" + ("+name" if affinity > 0 else ""),
                        "status": status,
                        "support": "low" if n < LOW_SUPPORT else "ok",
                        "confidence_basis": (
                            f"{matched} of {n} distinct ({a['name']}, {b['name']}) pairs exist as "
                            f"({pk[0]}, {pk[1]}) in {parent['name']}"
                        ),
                        "review_reasons": reasons,
                    }
                    rank = (status == "accepted", confidence, affinity)
                    if best_pair is None or rank > best_pair["_rank"]:
                        candidate["_rank"] = rank
                        best_pair = candidate
            if best_pair is None:
                continue
            link = (child["name"], tuple(best_pair["from_columns"]), parent["name"])
            if link in seen_links:
                continue
            seen_links.add(link)
            best_pair.pop("_rank", None)
            if best_pair["status"] == "accepted":
                found.append(best_pair)
            else:
                pending.append(best_pair)
    if review_out is not None:
        accepted_pairs = {(f["to_table"], f["from_table"]) for f in found}
        for cand in pending:
            # The mirror image of an accepted link is the same fact read backwards.
            if (cand["from_table"], cand["to_table"]) in accepted_pairs:
                continue
            review_out.append(cand)
    return sorted(found, key=lambda f: (f["from_table"], f["from_columns"]))


def _classify_tables(tables: List[Dict[str, Any]], fks: List[Dict[str, Any]]) -> None:
    incoming = Counter(fk["to_table"] for fk in fks if fk["to_table"] != fk["from_table"])
    outgoing = Counter(fk["from_table"] for fk in fks if fk["to_table"] != fk["from_table"])
    fk_cols = {(fk["from_table"], fk["from_column"]) for fk in fks}
    for table in tables:
        name = table["name"]
        for col in table["columns"]:
            if (name, col["name"]) in fk_cols and col["name"] not in table["primary_key"]:
                col["role"] = "foreign_key"
        measures = [c for c in table["columns"] if c["role"] in ("measure", "date")]
        non_key = [c for c in table["columns"] if c["role"] not in ("identifier", "foreign_key")]
        if incoming[name]:
            kind = "entity"
        elif outgoing[name] >= 2 and not non_key:
            kind = "link"
        elif outgoing[name] and (measures or len(table["primary_key"]) != 1):
            kind = "fact"
        elif outgoing[name]:
            kind = "entity"
        elif table["primary_key"]:
            kind = "entity"
        else:
            kind = "records"
        table["kind"] = kind
        table["incoming_references"] = incoming[name]
        table["outgoing_references"] = outgoing[name]


def profile_tables(
    tables: Dict[str, List[Dict[str, Any]]],
    source_row_counts: Optional[Dict[str, Optional[int]]] = None,
    *,
    min_fk_overlap: Optional[float] = None,
) -> Dict[str, Any]:
    """Profile every table and the relationships between them."""
    source_row_counts = source_row_counts or {}
    profiled = [
        _profile_table(name, rows, source_row_counts.get(name))
        for name, rows in tables.items()
    ]
    review: List[Dict[str, Any]] = []
    fks = discover_foreign_keys(profiled, min_fk_overlap, review_out=review)
    composite_review: List[Dict[str, Any]] = []
    composite_fks = discover_composite_foreign_keys(
        profiled, tables, min_fk_overlap, review_out=composite_review
    )
    _classify_tables(profiled, fks)

    warnings: List[str] = []
    for table in profiled:
        if table["row_count"] == 0:
            warnings.append(f"Table '{table['name']}' has no rows.")
        if table["is_sample"]:
            warnings.append(
                f"Table '{table['name']}' holds {table['row_count']:,} of "
                f"{table['source_row_count']:,} source rows (sample)."
            )
        if table["row_count"] and not table["primary_key"]:
            warnings.append(f"Table '{table['name']}' has no column (or pair) that uniquely identifies a row.")
        for col in table["columns"]:
            col.pop("_distinct", None)
            if table["row_count"] and col["null_rate"] == 1.0:
                warnings.append(f"Column '{table['name']}.{col['name']}' is empty in every row.")
            if col.get("date_format_ambiguous"):
                warnings.append(
                    f"Column '{table['name']}.{col['name']}' has dates that read the same as "
                    f"MM/DD and DD/MM; MM/DD/YYYY was assumed."
                )
            if col.get("mixed_native_types"):
                warnings.append(
                    f"Column '{table['name']}.{col['name']}' mixes value types "
                    f"{col['mixed_native_types']}; stored as text."
                )
    for fk in fks:
        if fk["orphan_values"]:
            warnings.append(
                f"{fk['from_table']}.{fk['from_column']} -> {fk['to_table']}.{fk['to_column']}: "
                f"{fk['orphan_values']} value(s) have no matching parent row."
            )
        if fk["support"] == "low":
            warnings.append(
                f"{fk['from_table']}.{fk['from_column']} -> {fk['to_table']}.{fk['to_column']}: "
                f"only {fk['distinct_values']} distinct value(s) support this link "
                f"(confidence {fk['confidence']:.2f})."
            )
    for cand in review:
        warnings.append(
            f"{cand['from_table']}.{cand['from_column']} -> {cand['to_table']}.{cand['to_column']} "
            f"needs review: {'; '.join(cand['review_reasons'])}. It is not used until it is accepted."
        )
    for cand in composite_review:
        warnings.append(
            f"{cand['from_table']}.({', '.join(cand['from_columns'])}) -> "
            f"{cand['to_table']}.({', '.join(cand['to_columns'])}) needs review: "
            f"{'; '.join(cand['review_reasons'])}."
        )

    total_rows = sum(t["row_count"] for t in profiled)
    known_source = [t["source_row_count"] for t in profiled if t["source_row_count"] is not None]
    return {
        "profile_version": 1,
        "tables": profiled,
        "foreign_keys": fks,
        # Plausible links that are not proven. Not used for joins, the graph,
        # or the ontology until a reviewer accepts them.
        "foreign_key_candidates": review + composite_review,
        "composite_foreign_keys": composite_fks,
        "warnings": warnings,
        "summary": {
            "table_count": len(profiled),
            "row_count": total_rows,
            "source_row_count": sum(known_source) if len(known_source) == len(profiled) else None,
            "is_sample": any(t["is_sample"] for t in profiled),
            "foreign_key_count": len(fks),
            "foreign_key_review_count": len(review) + len(composite_review),
            "composite_foreign_key_count": len(composite_fks),
            "tables_without_key": [t["name"] for t in profiled if t["row_count"] and not t["primary_key"]],
        },
    }


def _link_key(link: Dict[str, Any]) -> Tuple[str, Tuple[str, ...], str, Tuple[str, ...]]:
    """Identity of a link, the same for single-column and two-column forms."""
    from_cols = link.get("from_columns") or [link.get("from_column")]
    to_cols = link.get("to_columns") or [link.get("to_column")]
    return (
        str(link.get("from_table") or ""),
        tuple(str(c) for c in from_cols if c),
        str(link.get("to_table") or ""),
        tuple(str(c) for c in to_cols if c),
    )


def apply_relationship_decisions(profile: Dict[str, Any], decisions: Optional[List[Dict[str, Any]]]) -> int:
    """Apply reviewer decisions to the links that were listed for review.

    ``accept`` moves a candidate into the links the fabric uses (joins, graph,
    ontology) and records who accepted it. ``reject`` keeps it out and stops it
    from being listed again. Decisions about links that are no longer
    candidates are ignored, so a rebuild on changed data starts from the data.
    Returns how many decisions were applied.
    """
    if not decisions:
        return 0
    by_key = {_link_key(d): d for d in decisions}
    applied = 0
    remaining: List[Dict[str, Any]] = []
    for cand in profile.get("foreign_key_candidates") or []:
        decision = by_key.get(_link_key(cand))
        verdict = str((decision or {}).get("decision") or "").lower()
        if cand.get("status") != "needs_review" or verdict not in ("accept", "reject"):
            remaining.append(cand)
            continue
        applied += 1
        cand["reviewed_by"] = decision.get("by")
        cand["reviewed_at"] = decision.get("at")
        if verdict == "reject":
            cand["status"] = "rejected"
            remaining.append(cand)
            continue
        cand["status"] = "accepted_by_review"
        if cand.get("from_columns"):
            profile.setdefault("composite_foreign_keys", []).append(cand)
            continue
        profile.setdefault("foreign_keys", []).append(cand)
        table = table_by_name(profile, cand["from_table"])
        if table:
            for col in table["columns"]:
                if col["name"] == cand["from_column"] and col["name"] not in table["primary_key"]:
                    col["role"] = "foreign_key"
    profile["foreign_key_candidates"] = remaining
    profile.get("foreign_keys", []).sort(key=lambda f: (f["from_table"], f["from_column"]))
    summary = profile.setdefault("summary", {})
    summary["foreign_key_count"] = len(profile.get("foreign_keys") or [])
    summary["composite_foreign_key_count"] = len(profile.get("composite_foreign_keys") or [])
    summary["foreign_key_review_count"] = sum(
        1 for c in profile.get("foreign_key_candidates") or [] if c.get("status") == "needs_review"
    )
    return applied


def table_by_name(profile: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    return next((t for t in profile.get("tables", []) if t["name"] == name), None)


def split_rows_by_table(
    rows: Iterable[Dict[str, Any]],
    default_table: str = "records",
    table_key: str = "__source_collection",
) -> Dict[str, List[Dict[str, Any]]]:
    """Group a flat list of rows into tables using the ingestion stamp on each row."""
    tables: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        name = str(row.get(table_key) or default_table)
        tables.setdefault(name, []).append(row)
    return tables
