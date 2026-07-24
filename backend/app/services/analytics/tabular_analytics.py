"""
Full-fabric deterministic analytics for CSV / database row chunks.

Supports counts, distributions, group-by, filters, and numeric aggregates over
**all** indexed rows — never preview ``sample_rows`` or a tiny similarity window.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
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
    "grouped by",
    "grouping by",
    "group-by",
    "per ",
    "average",
    "avg",
    "mean",
    "median",
    "minimum",
    "maximum",
    "min ",
    "max ",
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
    "where ",
    "filter",
    "filtered",
    "only ",
    "with ",
    "greater than",
    "less than",
    "at least",
    "at most",
    "equal to",
    "equals",
    " vs ",
    "versus",
    "compare",
    "comparison",
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
    "release_status",
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
    "reading",
    "yield_pct",
)

# Soft NL tokens → column name patterns (suffix/contains), fabric-agnostic.
COLUMN_SYNONYMS: Dict[str, Tuple[str, ...]] = {
    "status": ("status", "outcome", "state", "disposition"),
    "outcome": ("outcome", "result", "disposition"),
    "result": ("result", "outcome"),
    "payer": ("payer",),
    "provider": ("provider",),
    "amount": ("amount", "paid", "billed", "allowed", "cost", "price"),
    "score": ("score",),
    "label": ("label", "class", "category"),
    "class": ("class", "label", "category"),
    "type": ("type", "kind", "category"),
    "state": ("state", "status"),
}


FilterSpec = Dict[str, Any]


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


def _find_column(text: str, columns: Sequence[str], *, min_len: int = 2) -> Optional[str]:
    """Match a column when a column token appears inside ``text`` (forward match)."""
    q = str(text or "").lower()
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
            if not variant or len(variant) < min_len:
                continue
            if variant in q or _norm_key(variant) in q_norm:
                score = len(_norm_key(variant))
                if best is None or score > best[0]:
                    best = (score, col)
    return best[1] if best else None


def _resolve_column_fragment(
    fragment: str,
    columns: Sequence[str],
    *,
    min_len: int = 3,
) -> Tuple[Optional[str], List[str]]:
    """
    Resolve a short NL fragment (e.g. ``status``) to a fabric column.

    Priority: exact → suffix → synonym pattern → contains.
    Returns ``(resolved_or_none, candidates)``. When multiple strong matches
    exist, ``resolved`` is None and ``candidates`` lists the options.
    """
    raw = str(fragment or "").strip(" .,;:?!\"'")
    if not raw:
        return None, []
    frag_l = raw.lower().strip()
    frag_norm = _norm_key(frag_l)
    if len(frag_norm) < 2:
        return None, []

    exact: List[str] = []
    suffix: List[str] = []
    synonym: List[str] = []
    contains: List[str] = []

    for col in columns:
        col_l = col.lower()
        col_norm = _norm_key(col)
        col_spaced = col_l.replace("_", " ")
        if (
            col_norm == frag_norm
            or col_l == frag_l
            or col_spaced == frag_l
            or col_l.replace("_", "") == frag_l.replace(" ", "")
        ):
            exact.append(col)
            continue
        if len(frag_norm) >= min_len and (
            col_norm.endswith(frag_norm)
            or col_l.endswith("_" + frag_l)
            or col_l.endswith(frag_l)
            or col_spaced.endswith(frag_l)
        ):
            suffix.append(col)
            continue
        if len(frag_norm) >= min_len and frag_norm in col_norm:
            contains.append(col)

    # Synonym / alias layer (status → *status*, *outcome*, …)
    for syn_key, patterns in COLUMN_SYNONYMS.items():
        if frag_norm != _norm_key(syn_key) and frag_l != syn_key:
            continue
        for col in columns:
            col_l = col.lower()
            col_norm = _norm_key(col)
            if any(p in col_l or _norm_key(p) in col_norm for p in patterns):
                synonym.append(col)

    def _uniq(items: List[str]) -> List[str]:
        out: List[str] = []
        seen = set()
        # Prefer longer (more specific) names first within a bucket.
        for col in sorted(items, key=lambda c: (-len(_norm_key(c)), c.lower())):
            if col in seen:
                continue
            seen.add(col)
            out.append(col)
        return out

    for bucket in (exact, suffix, synonym, contains):
        uniq = _uniq(bucket)
        if not uniq:
            continue
        if len(uniq) == 1:
            return uniq[0], uniq
        # Multiple strong matches → do not guess; caller may clarify.
        return None, uniq

    return None, []


def _find_all_columns(text: str, columns: Sequence[str]) -> List[str]:
    """Return all columns mentioned in text, longest match first (no nested dups)."""
    hits: List[Tuple[int, str]] = []
    q = str(text or "").lower()
    q_norm = _norm_key(q)
    for col in columns:
        variants = {
            col.lower(),
            col.lower().replace("_", " "),
            col.lower().replace("_", ""),
            _norm_key(col),
        }
        for variant in variants:
            if not variant or len(variant) < 2:
                continue
            if variant in q or _norm_key(variant) in q_norm:
                hits.append((len(_norm_key(col)), col))
                break
    # Also pick up soft fragments via resolve (status → adjudication_status).
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", q):
        resolved, _cands = _resolve_column_fragment(token, columns)
        if resolved:
            hits.append((len(_norm_key(resolved)), resolved))
    hits.sort(key=lambda x: -x[0])
    out: List[str] = []
    seen = set()
    for _, col in hits:
        if col in seen:
            continue
        seen.add(col)
        out.append(col)
    return out


def is_analytical_query(query: str, columns: Optional[Sequence[str]] = None) -> bool:
    """True when the question asks for counts, distributions, group-by, filters, or aggregates."""
    q = str(query or "").strip().lower()
    if not q:
        return False
    if any(token in q for token in ANALYTICAL_TOKENS):
        return True
    if re.search(r"\bby\b", q) and any(tok in q for tok in ("count", "sum", "avg", "average", "mean", "total", "per")):
        return True
    if re.search(r"[><=]=?", q) and re.search(r"\d", q):
        return True
    hits = sum(1 for label in CATEGORY_HINT_LABELS if re.search(rf"\b{re.escape(label)}\b", q))
    if hits >= 1 and any(tok in q for tok in ("how many", "count", "number", "only", "with", "where", "filter")):
        return True
    if hits >= 2:
        return True
    # Schema-aware: query mentions a fabric column + analytical verb-ish phrasing
    if columns:
        mentioned = _find_all_columns(q, columns)
        if mentioned and (
            any(tok in q for tok in ("how", "what", "show", "list", "give", "find", "get", "which"))
            or re.search(r"[><=]", q)
            or "by" in q
        ):
            return True
    return False


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
    sample_vals: List[str] = []
    for r in rows[:200]:
        if column not in r:
            continue
        raw = r.get(column)
        if raw is None or str(raw).strip() == "":
            continue
        sample_vals.append(str(raw).strip())
    if not sample_vals:
        return False
    hits = sum(1 for v in sample_vals if _to_float(v) is not None)
    return (hits / len(sample_vals)) >= 0.6


def _pick_categorical_field(
    rows: Sequence[Dict[str, str]],
    query: str,
    *,
    exclude: Optional[Sequence[str]] = None,
) -> Optional[str]:
    columns = _columns(rows)
    exclude_set = {_norm_key(x) for x in (exclude or [])}
    mentioned = _find_column(query, columns)
    if mentioned and _norm_key(mentioned) not in exclude_set and not _column_is_mostly_numeric(rows, mentioned):
        return mentioned
    # Soft tokens in query (status, outcome, …)
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", str(query or "")):
        resolved, _cands = _resolve_column_fragment(token, columns)
        if (
            resolved
            and _norm_key(resolved) not in exclude_set
            and not _column_is_mostly_numeric(rows, resolved)
        ):
            return resolved
    if mentioned and _norm_key(mentioned) not in exclude_set:
        # Mentioned numeric field is not categorical
        pass
    lower_map = {_norm_key(c): c for c in columns}
    for preferred in PREFERRED_CATEGORICAL_FIELDS:
        hit = lower_map.get(_norm_key(preferred))
        if hit and _norm_key(hit) not in exclude_set:
            return hit
    sample = rows[: min(200, len(rows))]
    best_col = None
    best_score = -1.0
    for col in columns:
        if _norm_key(col) in exclude_set:
            continue
        values = [str(r.get(col, "")).strip() for r in sample if str(r.get(col, "")).strip()]
        if len(values) < max(3, len(sample) // 5):
            continue
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


def _pick_numeric_field(
    rows: Sequence[Dict[str, str]],
    query: str,
    *,
    exclude: Optional[Sequence[str]] = None,
) -> Optional[str]:
    columns = _columns(rows)
    exclude_set = {_norm_key(x) for x in (exclude or [])}
    mentioned_all = _find_all_columns(query, columns)
    for mentioned in mentioned_all:
        if _norm_key(mentioned) in exclude_set:
            continue
        if _column_is_mostly_numeric(rows, mentioned):
            return mentioned
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", str(query or "")):
        if token.lower() in {"group", "by", "count", "average", "mean", "sum", "how", "many", "what", "the"}:
            continue
        resolved, _cands = _resolve_column_fragment(token, columns)
        if (
            resolved
            and _norm_key(resolved) not in exclude_set
            and _column_is_mostly_numeric(rows, resolved)
        ):
            return resolved
    lower_map = {_norm_key(c): c for c in columns}
    for preferred in PREFERRED_NUMERIC_FIELDS:
        hit = lower_map.get(_norm_key(preferred))
        if hit and _norm_key(hit) not in exclude_set and _column_is_mostly_numeric(rows, hit):
            return hit
    for col in columns:
        if _norm_key(col) in exclude_set:
            continue
        kl = col.lower()
        if any(tok in kl for tok in ("score", "amount", "value", "qty", "quantity", "rate", "percent", "reading", "yield")):
            if _column_is_mostly_numeric(rows, col):
                return col
    for col in columns:
        if _norm_key(col) in exclude_set:
            continue
        if _column_is_mostly_numeric(rows, col):
            return col
    return None


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
        # Word-boundary match so "Active" does not hit inside "ACTIVITY".
        if re.search(rf"\b{re.escape(label.lower())}\b", lower):
            found.append(label)
    return found


def _value_inventory(rows: Sequence[Dict[str, str]], limit_per_col: int = 40) -> Dict[str, List[str]]:
    """Map column -> frequent distinct values (for filter value matching)."""
    inventory: Dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows[: min(2000, len(rows))]:
        for key, value in row.items():
            text = str(value).strip()
            if text:
                inventory[key][text] += 1
    return {
        col: [v for v, _ in counter.most_common(limit_per_col)]
        for col, counter in inventory.items()
    }


def _match_value_to_column(
    value: str,
    rows: Sequence[Dict[str, str]],
    columns: Sequence[str],
    *,
    preferred_field: Optional[str] = None,
) -> Optional[Tuple[str, str]]:
    """Find (column, canonical_value) for a free-text value like Active."""
    want = str(value or "").strip()
    if not want:
        return None
    want_l = want.lower()
    inventory = _value_inventory(rows)
    search_cols = list(columns)
    if preferred_field and preferred_field in search_cols:
        search_cols = [preferred_field] + [c for c in search_cols if c != preferred_field]
    # Prefer categorical-looking columns
    search_cols = sorted(
        search_cols,
        key=lambda c: (0 if not _column_is_mostly_numeric(rows, c) else 1, c.lower()),
    )
    for col in search_cols:
        for candidate in inventory.get(col, []):
            if candidate.lower() == want_l:
                return col, candidate
    for col in search_cols:
        for candidate in inventory.get(col, []):
            if want_l in candidate.lower() or candidate.lower() in want_l:
                if len(want_l) >= 3:
                    return col, candidate
    return None


def _group_by_requested(query: str) -> bool:
    q = str(query or "").lower()
    return bool(
        re.search(
            r"group(?:ed|ing)?\s*by|breakdown\s+by|count(?:s)?\s+by|"
            r"\baverage\b.+\bby\b|\bavg\b.+\bby\b|\bsum\b.+\bby\b|\bper\b\s+[a-z0-9_]",
            q,
        )
    )


def extract_group_by_fragment(query: str) -> Optional[str]:
    """Return the raw group-by fragment from the question (before column resolve)."""
    q = str(query or "")
    patterns = [
        r"group(?:ed|ing)?\s*by\s+([A-Za-z0-9_ ]+?)(?:\s+and\s+|\s*,|\s*$|\s+with|\s+where|\s+for|\s+having)",
        r"breakdown\s+by\s+([A-Za-z0-9_ ]+?)(?:\s+and\s+|\s*,|\s*$|\s+with|\s+where)",
        r"\bper\s+([A-Za-z0-9_ ]+?)(?:\s+and\s+|\s*,|\s*$|\s+with|\s+where)",
        r"count(?:s)?\s+by\s+([A-Za-z0-9_ ]+)",
        r"average\s+.+\s+by\s+([A-Za-z0-9_ ]+)",
        r"avg\s+.+\s+by\s+([A-Za-z0-9_ ]+)",
        r"sum\s+.+\s+by\s+([A-Za-z0-9_ ]+)",
        r"\bby\s+([A-Za-z0-9_ ]+?)(?:\s+and\s+|\s*,|\s*$|\s+with|\s+where|\s+for\b)",
    ]
    for pattern in patterns:
        match = re.search(pattern, q, flags=re.IGNORECASE)
        if not match:
            continue
        fragment = match.group(1).strip(" .,;:?")
        fragment = re.split(
            r"\b(?:with|where|that|which|and|or|for|in|on|of|the)\b",
            fragment,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip(" .,;:?")
        if fragment:
            return fragment
    return None


def extract_group_by_field(
    query: str,
    columns: Sequence[str],
) -> Tuple[Optional[str], Optional[str], List[str]]:
    """
    Parse and resolve group-by field.

    Returns ``(resolved_column, raw_fragment, candidates)``.
    """
    fragment = extract_group_by_fragment(query)
    if not fragment:
        return None, None, []
    # Prefer soft resolve (status → adjudication_status); fall back to forward match.
    resolved, candidates = _resolve_column_fragment(fragment, columns)
    if resolved:
        return resolved, fragment, candidates
    forward = _find_column(fragment, columns)
    if forward:
        return forward, fragment, [forward]
    return None, fragment, candidates


def format_unresolved_group_by_answer(
    fabric_name: str,
    fragment: str,
    columns: Sequence[str],
    candidates: Sequence[str],
) -> str:
    col_list = list(candidates) if candidates else list(columns)[:20]
    rows = [[c] for c in col_list]
    note = (
        f"Could not uniquely map **group by `{fragment}`** to a column in **{fabric_name}**."
        if candidates
        else f"No column matched **group by `{fragment}`** in **{fabric_name}**."
    )
    return "\n".join(
        [
            "## Needs clarification",
            note,
            "",
            "Please retry with an exact column name, for example:",
            "",
            markdown_table(["Candidate columns"], rows or [["(no columns found)"]]),
            "",
            "### Notes",
            "- Analytics did **not** fall back to a total-row count for this group-by question.",
        ]
    )


def extract_filters(query: str, rows: Sequence[Dict[str, str]]) -> List[FilterSpec]:
    """Extract equality and comparison filters from natural language."""
    columns = _columns(rows)
    q = str(query or "")
    filters: List[FilterSpec] = []
    used_spans: List[Tuple[int, int]] = []

    def _overlap(start: int, end: int) -> bool:
        return any(not (end <= a or start >= b) for a, b in used_spans)

    def _resolve_field(field_frag: str) -> Optional[str]:
        resolved, _cands = _resolve_column_fragment(field_frag, columns)
        if resolved:
            return resolved
        return _find_column(field_frag, columns)

    # Numeric comparisons: score > 40, amount >= 100, FIELD less than 5
    cmp_patterns = [
        (
            r"([A-Za-z][A-Za-z0-9_ ]{1,40}?)\s*(>=|<=|>|<|==|=)\s*(-?\d+(?:\.\d+)?)",
            None,
        ),
        (
            r"([A-Za-z][A-Za-z0-9_ ]{1,40}?)\s+(?:greater than|more than|over|above)\s+(-?\d+(?:\.\d+)?)",
            ">",
        ),
        (
            r"([A-Za-z][A-Za-z0-9_ ]{1,40}?)\s+(?:less than|under|below)\s+(-?\d+(?:\.\d+)?)",
            "<",
        ),
        (
            r"([A-Za-z][A-Za-z0-9_ ]{1,40}?)\s+(?:at least|no less than)\s+(-?\d+(?:\.\d+)?)",
            ">=",
        ),
        (
            r"([A-Za-z][A-Za-z0-9_ ]{1,40}?)\s+(?:at most|no more than)\s+(-?\d+(?:\.\d+)?)",
            "<=",
        ),
    ]
    for pattern, fixed_op in cmp_patterns:
        for match in re.finditer(pattern, q, flags=re.IGNORECASE):
            if _overlap(match.start(), match.end()):
                continue
            field_frag = match.group(1).strip()
            if fixed_op is None:
                op = match.group(2)
                number = float(match.group(3))
            else:
                op = fixed_op
                number = float(match.group(2))
            col = _resolve_field(field_frag)
            if not col:
                continue
            filters.append({"field": col, "op": op if op != "==" else "=", "value": number, "kind": "compare"})
            used_spans.append((match.start(), match.end()))

    # Equality: where status = Active / outcome is Inactive / status equals FAIL
    eq_patterns = [
        r"(?:where|with|only|for)\s+([A-Za-z][A-Za-z0-9_ ]{1,40}?)\s*(?:=|==|equals|equal to|is|:)\s*[\"']?([A-Za-z0-9_\- ]+?)[\"']?(?=\s+(?:and|or|with|where|group|by|that|,|\.|$)|\s*$)",
        r"([A-Za-z][A-Za-z0-9_]{2,40})\s*(?:=|==)\s*[\"']?([A-Za-z0-9_\- ]+?)[\"']?(?=\s+(?:and|or|with|where|group|by|,|\.|$)|\s*$)",
        r"([A-Za-z][A-Za-z0-9_ ]{1,40}?)\s+is\s+[\"']?([A-Za-z0-9_\- ]+?)[\"']?(?=\s+(?:and|or|with|where|group|by|that|,|\.|$)|\s*$)",
    ]
    for pattern in eq_patterns:
        for match in re.finditer(pattern, q, flags=re.IGNORECASE):
            if _overlap(match.start(), match.end()):
                continue
            field_frag = match.group(1).strip()
            value_frag = match.group(2).strip(" .,;:?")
            if value_frag.lower() in {"the", "a", "an", "this", "that", "there", "it"}:
                continue
            col = _resolve_field(field_frag)
            if not col:
                continue
            matched = _match_value_to_column(value_frag, rows, [col], preferred_field=col)
            canon = matched[1] if matched else value_frag
            filters.append({"field": col, "op": "=", "value": canon, "kind": "equals"})
            used_spans.append((match.start(), match.end()))

    # Bare category labels as filters: "only Active", "Active compounds with..."
    labels = _extract_target_labels(q)
    q_lower = q.lower()
    listing_distribution = (
        len(labels) >= 2
        and any(tok in q_lower for tok in ("how many", "count", "distribution", "breakdown", "vs", "versus", "and"))
        and not any(tok in q_lower for tok in ("only", "where", "filter", "with score", "greater", "less", ">"))
    )
    if not listing_distribution:
        for label in labels:
            if any(str(f.get("value", "")).lower() == label.lower() for f in filters):
                continue
            if len(labels) >= 2 and "only" not in q_lower and "where" not in q_lower:
                if not re.search(rf"\b{re.escape(label)}\b.{{0,40}}(with|>|<|greater|less|at least|at most|score|amount)", q, re.I):
                    if not re.search(rf"(only|where|filter).{{0,20}}\b{re.escape(label)}\b", q, re.I):
                        continue
            matched = _match_value_to_column(label, rows, columns)
            if not matched:
                continue
            col, canon = matched
            if any(f.get("field") == col and str(f.get("value", "")).lower() == canon.lower() for f in filters):
                continue
            filters.append({"field": col, "op": "=", "value": canon, "kind": "equals"})

    return filters


def apply_filters(rows: Sequence[Dict[str, str]], filters: Sequence[FilterSpec]) -> List[Dict[str, str]]:
    if not filters:
        return list(rows)
    out: List[Dict[str, str]] = []
    for row in rows:
        ok = True
        for spec in filters:
            field = str(spec.get("field") or "")
            op = str(spec.get("op") or "=")
            expected = spec.get("value")
            raw = row.get(field)
            if op in {">", ">=", "<", "<="}:
                left = _to_float(raw)
                right = _to_float(expected)
                if left is None or right is None:
                    ok = False
                    break
                if op == ">" and not (left > right):
                    ok = False
                elif op == ">=" and not (left >= right):
                    ok = False
                elif op == "<" and not (left < right):
                    ok = False
                elif op == "<=" and not (left <= right):
                    ok = False
            else:
                left = str(raw or "").strip().lower()
                right = str(expected or "").strip().lower()
                if left != right:
                    ok = False
                    break
        if ok:
            out.append(row)
    return out


def _format_filter_clause(filters: Sequence[FilterSpec]) -> str:
    if not filters:
        return ""
    parts = []
    for spec in filters:
        field = spec.get("field")
        op = spec.get("op")
        value = spec.get("value")
        parts.append(f"`{field}` {op} {value}")
    return " AND ".join(parts)


def _wants_total_only(query: str, columns: Sequence[str], filters: Sequence[FilterSpec], group_by: Optional[str]) -> bool:
    if filters or group_by:
        return False
    q = str(query or "").strip().lower()
    if not any(tok in q for tok in ("how many", "count", "number of", "total")):
        return False
    if _extract_target_labels(query):
        return False
    if _find_column(query, columns):
        if any(tok in q for tok in ("unique", "distinct", "average", "avg", "mean", "median", "min", "max", "sum")):
            return False
        return False
    entity_tokens = (
        "compound", "compounds", "row", "rows", "record", "records",
        "entry", "entries", "item", "items", "claim", "claims", "total",
    )
    return any(tok in q for tok in entity_tokens) or q.strip() in {
        "count", "total", "how many", "number of rows", "total rows", "row count",
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
    median = numbers[mid] if n % 2 else (numbers[mid - 1] + numbers[mid]) / 2.0
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
    header_cells = [str(h) for h in headers]
    lines = [
        "| " + " | ".join(header_cells) + " |",
        "| " + " | ".join(["---"] * len(header_cells)) + " |",
    ]
    for row in rows:
        cells = [str(c) if c is not None else "" for c in row]
        while len(cells) < len(header_cells):
            cells.append("")
        cells = cells[: len(header_cells)]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


_markdown_table = markdown_table


def format_total_rows_answer(
    fabric_name: str,
    row_total: int,
    *,
    note: str = "",
    filter_clause: str = "",
    unfiltered_total: Optional[int] = None,
) -> str:
    if filter_clause:
        metric_rows: List[List[Any]] = []
        if unfiltered_total is not None:
            metric_rows.append(["Rows before filter", unfiltered_total])
        metric_rows.append(["Matching rows", row_total])
        metric_rows.append(["Filter", filter_clause])
    else:
        metric_rows = [["Total rows / compounds", row_total]]
    parts = [
        "## Summary",
        f"Full-fabric row count for **{fabric_name}**.",
        "",
        markdown_table(["Metric", "Value"], metric_rows),
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
    *,
    filter_clause: str = "",
) -> str:
    rows = [
        [f"Distinct `{field}`", distinct],
        ["Rows scanned", row_total],
    ]
    if filter_clause:
        rows.append(["Filter", filter_clause])
    return "\n".join(
        [
            "## Summary",
            f"Distinct values of `{field}` in **{fabric_name}**.",
            "",
            markdown_table(["Metric", "Value"], rows),
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
    filter_clause: str = "",
) -> str:
    rows = [
        ["Count (numeric)", int(stats["count"])],
        ["Min", _fmt_number(stats["min"])],
        ["Max", _fmt_number(stats["max"])],
        ["Average", _fmt_number(stats["average"])],
        ["Median", _fmt_number(stats["median"])],
        ["Sum", _fmt_number(stats["sum"])],
    ]
    if filter_clause:
        rows.append(["Filter", filter_clause])
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
            markdown_table(["Statistic", "Value"], rows),
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
    filter_clause: str = "",
    group_by: Optional[str] = None,
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
    if group_by:
        headers = [group_by if h == "Category" else h for h in headers]
    if include_pct:
        table_rows.append(["**Total**", counted, "100.00%"])
    else:
        table_rows.append(["**Total**", counted])
    title_bits = [f"Distribution of `{field}`" if not group_by else f"Group-by `{field}`"]
    title_bits.append(f"in **{fabric_name}** (full indexed fabric).")
    intro = " ".join(title_bits)
    if filter_clause:
        intro += f" Filter: {filter_clause}."
    return "\n".join(
        [
            "## Summary",
            intro,
            "",
            markdown_table(headers, table_rows),
            "",
            "### Notes",
            "- Totals are computed over **all indexed row chunks**, not preview `sample_rows`.",
        ]
    )


def format_group_agg_answer(
    fabric_name: str,
    group_field: str,
    value_field: str,
    agg: str,
    grouped_rows: List[List[Any]],
    *,
    filter_clause: str = "",
) -> str:
    headers = [group_field, "Count", agg.capitalize(), "Min", "Max"]
    intro = f"`{agg}` of `{value_field}` grouped by `{group_field}` in **{fabric_name}**."
    if filter_clause:
        intro += f" Filter: {filter_clause}."
    return "\n".join(
        [
            "## Summary",
            intro,
            "",
            markdown_table(headers, grouped_rows),
            "",
            "### Notes",
            "- Computed over **all indexed row chunks**, not preview `sample_rows`.",
        ]
    )


def _grouped_numeric_table(
    rows: Sequence[Dict[str, str]],
    group_field: str,
    value_field: str,
    agg: str,
) -> List[List[Any]]:
    buckets: Dict[str, List[float]] = defaultdict(list)
    for row in rows:
        key = str(row.get(group_field, "")).strip() or "(blank)"
        number = _to_float(row.get(value_field))
        if number is not None:
            buckets[key].append(number)
    table: List[List[Any]] = []
    for key in sorted(buckets.keys(), key=lambda k: (-len(buckets[k]), k.lower())):
        nums = sorted(buckets[key])
        n = len(nums)
        if not n:
            continue
        stats = {
            "count": n,
            "sum": sum(nums),
            "average": sum(nums) / n,
            "min": nums[0],
            "max": nums[-1],
            "median": nums[n // 2] if n % 2 else (nums[n // 2 - 1] + nums[n // 2]) / 2.0,
        }
        table.append(
            [
                key,
                n,
                _fmt_number(stats[agg]),
                _fmt_number(stats["min"]),
                _fmt_number(stats["max"]),
            ]
        )
    return table


def analyze_tabular_query(
    rows: Sequence[Dict[str, str]],
    query: str,
    *,
    fabric_name: str = "knowledge fabric",
) -> Optional[Dict[str, Any]]:
    """
    Run deterministic analytics over all provided rows.

    Supports group-by, filters, counts, distributions, and numeric aggregates.
    """
    if not rows:
        return None

    columns = _columns(rows)
    if not is_analytical_query(query, columns=columns):
        return None

    unfiltered_total = len(rows)
    filters = extract_filters(query, rows)
    filtered_rows = apply_filters(rows, filters)
    filter_clause = _format_filter_clause(filters)
    group_by, group_fragment, group_candidates = extract_group_by_field(query, columns)
    labels = _extract_target_labels(query)
    # If labels were applied as filters, don't also force distribution ordering on them
    label_filters = [f for f in filters if f.get("kind") == "equals" and str(f.get("value")) in labels]
    distribution_labels = [] if label_filters and len(labels) == 1 else labels
    if group_by and distribution_labels and len(distribution_labels) >= 2 and not label_filters:
        distribution_labels = labels

    unique_intent = _wants_unique(query)
    numeric_intent = _wants_numeric_agg(query)
    row_total = len(filtered_rows)

    # Group-by requested but column unresolved → clarify (never silent total_rows).
    if group_fragment and not group_by and _group_by_requested(query):
        return {
            "intent": "group_by_unresolved",
            "row_total": unfiltered_total,
            "answer": format_unresolved_group_by_answer(
                fabric_name,
                group_fragment,
                columns,
                group_candidates,
            ),
            "metrics": {
                "fragment": group_fragment,
                "candidates": list(group_candidates),
                "columns": list(columns)[:40],
            },
            "filters": filters,
            "group_by": None,
        }

    # Filtered empty set
    if filters and row_total == 0:
        return {
            "intent": "filtered_empty",
            "row_total": 0,
            "answer": format_total_rows_answer(
                fabric_name,
                0,
                filter_clause=filter_clause,
                unfiltered_total=unfiltered_total,
                note="No rows matched the requested filter(s).",
            ),
            "metrics": {
                "row_total": 0,
                "unfiltered_total": unfiltered_total,
                "filters": filters,
            },
            "filters": filters,
            "group_by": group_by,
        }

    # Group-by + numeric aggregate: average score by outcome
    if group_by and numeric_intent:
        value_field = _pick_numeric_field(filtered_rows or rows, query, exclude=[group_by])
        if value_field and value_field != group_by:
            table = _grouped_numeric_table(filtered_rows, group_by, value_field, numeric_intent)
            if table:
                return {
                    "intent": f"group_{numeric_intent}",
                    "row_total": row_total,
                    "field": value_field,
                    "group_by": group_by,
                    "answer": format_group_agg_answer(
                        fabric_name,
                        group_by,
                        value_field,
                        numeric_intent,
                        table,
                        filter_clause=filter_clause,
                    ),
                    "metrics": {
                        "group_by": group_by,
                        "field": value_field,
                        "agg": numeric_intent,
                        "groups": len(table),
                        "row_total": row_total,
                        "filters": filters,
                    },
                    "filters": filters,
                }

    # Group-by counts / breakdown by X
    if group_by:
        counts = _order_counts(_value_counts(filtered_rows, group_by), distribution_labels)
        return {
            "intent": "group_by_counts",
            "row_total": row_total,
            "field": group_by,
            "group_by": group_by,
            "answer": format_value_counts_answer(
                fabric_name,
                group_by,
                counts,
                include_pct=True,
                filter_clause=filter_clause,
                group_by=group_by,
            ),
            "metrics": {
                "field": group_by,
                "counts": counts,
                "row_total": row_total,
                "filters": filters,
            },
            "filters": filters,
        }

    # Bare / filtered total
    if _wants_total_only(query, columns, filters, group_by) and not unique_intent and not numeric_intent:
        return {
            "intent": "total_rows" if not filters else "filtered_count",
            "row_total": row_total,
            "answer": format_total_rows_answer(
                fabric_name,
                row_total,
                filter_clause=filter_clause,
                unfiltered_total=unfiltered_total if filters else None,
            ),
            "metrics": {
                "row_total": row_total,
                "unfiltered_total": unfiltered_total,
                "filters": filters,
            },
            "filters": filters,
        }

    # Filtered count without other intent: "how many Active with score > 40"
    if filters and not unique_intent and not numeric_intent and any(
        tok in str(query).lower() for tok in ("how many", "count", "number of", "total")
    ):
        # If also asking for a categorical breakdown of remaining dimension, prefer that
        field = _pick_categorical_field(filtered_rows or rows, query)
        filter_fields = {_norm_key(str(f.get("field"))) for f in filters}
        if field and _norm_key(field) not in filter_fields and len(_value_counts(filtered_rows, field)) > 1:
            counts = _order_counts(_value_counts(filtered_rows, field), distribution_labels)
            return {
                "intent": "filtered_value_counts",
                "row_total": row_total,
                "field": field,
                "answer": format_value_counts_answer(
                    fabric_name,
                    field,
                    counts,
                    include_pct=True,
                    filter_clause=filter_clause,
                ),
                "metrics": {"field": field, "counts": counts, "row_total": row_total, "filters": filters},
                "filters": filters,
            }
        return {
            "intent": "filtered_count",
            "row_total": row_total,
            "answer": format_total_rows_answer(
                fabric_name,
                row_total,
                filter_clause=filter_clause,
                unfiltered_total=unfiltered_total,
            ),
            "metrics": {
                "row_total": row_total,
                "unfiltered_total": unfiltered_total,
                "filters": filters,
            },
            "filters": filters,
        }

    # Unique / distinct
    if unique_intent:
        field = _find_column(query, columns) or _pick_categorical_field(filtered_rows or rows, query)
        if not field:
            return None
        values = {str(r.get(field, "")).strip() for r in filtered_rows if str(r.get(field, "")).strip()}
        return {
            "intent": "unique_count",
            "row_total": row_total,
            "field": field,
            "answer": format_unique_count_answer(
                fabric_name, field, len(values), row_total, filter_clause=filter_clause
            ),
            "metrics": {"field": field, "distinct": len(values), "row_total": row_total, "filters": filters},
            "filters": filters,
        }

    # Numeric aggregates (optionally filtered)
    if numeric_intent:
        field = _pick_numeric_field(filtered_rows or rows, query)
        if not field:
            return None
        stats = _numeric_stats(filtered_rows, field)
        if not stats:
            return None
        return {
            "intent": f"numeric_{numeric_intent}",
            "row_total": row_total,
            "field": field,
            "answer": format_numeric_answer(
                fabric_name,
                field,
                stats,
                highlight=numeric_intent,
                title=f"{numeric_intent.capitalize()} of `{field}`",
                filter_clause=filter_clause,
            ),
            "metrics": {"field": field, **stats, "filters": filters},
            "filters": filters,
        }

    # Categorical distribution
    field = _pick_categorical_field(filtered_rows or rows, query)
    if field and _column_is_mostly_numeric(filtered_rows or rows, field):
        uniq_estimate = len(
            {str(r.get(field, "")).strip() for r in (filtered_rows or rows)[:500] if str(r.get(field, "")).strip()}
        )
        if uniq_estimate > 40 or not distribution_labels:
            stats = _numeric_stats(filtered_rows, field)
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
                        filter_clause=filter_clause,
                    ),
                    "metrics": {"field": field, **stats, "filters": filters},
                    "filters": filters,
                }

    if not field:
        if any(tok in str(query).lower() for tok in ("how many", "count", "total", "number of")) or filters:
            return {
                "intent": "total_rows" if not filters else "filtered_count",
                "row_total": row_total,
                "answer": format_total_rows_answer(
                    fabric_name,
                    row_total,
                    filter_clause=filter_clause,
                    unfiltered_total=unfiltered_total if filters else None,
                    note="No categorical field could be inferred for a breakdown.",
                ),
                "metrics": {"row_total": row_total, "filters": filters},
                "filters": filters,
            }
        return None

    counts = _order_counts(_value_counts(filtered_rows, field), distribution_labels)
    return {
        "intent": "value_counts",
        "row_total": row_total,
        "field": field,
        "answer": format_value_counts_answer(
            fabric_name,
            field,
            counts,
            include_pct=True,
            filter_clause=filter_clause,
        ),
        "metrics": {"field": field, "counts": counts, "row_total": row_total, "filters": filters},
        "filters": filters,
    }


def build_fabric_analytics_snapshot(
    rows: Sequence[Dict[str, str]],
    *,
    fabric_name: str = "knowledge fabric",
    max_categories: int = 12,
) -> Optional[str]:
    """
    Compact full-fabric snapshot for LLM context so sample chunks cannot
    masquerade as population totals.
    """
    if not rows:
        return None
    columns = _columns(rows)
    lines = [
        f"FULL-FABRIC ANALYTICS SNAPSHOT for '{fabric_name}'",
        f"Indexed row chunks: {len(rows)}",
        f"Columns: {', '.join(columns[:30])}" + ("…" if len(columns) > 30 else ""),
        "Do NOT compute population totals from retrieved sample chunks. Use these figures or request a deterministic analytics answer.",
    ]
    cat = None
    for preferred in PREFERRED_CATEGORICAL_FIELDS:
        for col in columns:
            if _norm_key(col) == _norm_key(preferred):
                cat = col
                break
        if cat:
            break
    if not cat:
        cat = _pick_categorical_field(rows, "")
    if cat:
        counts = _value_counts(rows, cat)
        lines.append(f"Distribution of `{cat}` (full fabric):")
        for label, value in list(counts.items())[:max_categories]:
            pct = 100.0 * float(value) / float(len(rows)) if rows else 0.0
            lines.append(f"- {label}: {value} ({pct:.2f}%)")
        if len(counts) > max_categories:
            lines.append(f"- … {len(counts) - max_categories} more categories")
    num = _pick_numeric_field(rows, "")
    if num:
        stats = _numeric_stats(rows, num)
        if stats:
            lines.append(
                f"Numeric `{num}` (full fabric): count={int(stats['count'])}, "
                f"min={_fmt_number(stats['min'])}, max={_fmt_number(stats['max'])}, "
                f"avg={_fmt_number(stats['average'])}"
            )
    return "\n".join(lines)


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
