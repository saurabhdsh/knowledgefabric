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
    "outcome_label",
    "PUBCHEM_ACTIVITY_OUTCOME",
    "activity_outcome",
    "ACTIVITY_OUTCOME",
    "outcome.phenotype",
    "outcome.source_label",
    "outcome",
    "duplicate_match_type",
    "match_type",
    "label",
    "status",
    "class",
    "result",
    "decision_route",
    "release_status",
    "dataset_id",
    "assay_id",
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


def _flatten_nested_value(key: str, value: str, into: Dict[str, str]) -> None:
    """
    Flatten nested dict-like field values (Python / JSON) into sibling keys.

    Example: outcome = "{'source_label': 'Inactive', 'phenotype': 'Inactive'}"
    → outcome retained raw, plus outcome.source_label / outcome.phenotype, and
      a normalized outcome_label for analytics.
    """
    raw = str(value or "").strip()
    if not raw or raw[0] not in "{[":
        return
    nested: Any = None
    try:
        import ast
        import json

        try:
            nested = ast.literal_eval(raw)
        except Exception:
            nested = json.loads(raw.replace("None", "null").replace("'", '"'))
    except Exception:
        return
    if not isinstance(nested, dict):
        return
    for nk, nv in nested.items():
        child_key = f"{key}.{nk}"
        if nv is None:
            into[child_key] = ""
        elif isinstance(nv, (dict, list)):
            into[child_key] = str(nv)
        else:
            into[child_key] = str(nv).strip()
    if key.lower() in {"outcome", "activity_outcome", "pubchem_activity_outcome"}:
        for label_key in ("phenotype", "source_label", "standard_label", "label"):
            cand = nested.get(label_key)
            if cand is not None and str(cand).strip() and str(cand).strip().lower() not in {
                "none",
                "null",
                "nan",
            }:
                into["outcome_label"] = str(cand).strip()
                break


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
            _flatten_nested_value(k, v, parsed)
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
        if not row:
            continue
        # Preserve source/file hints so multi-assay joins (CYP2C9 vs CYP2D6 …) work.
        for meta_key, row_key in (
            ("source_name", "_source_name"),
            ("source_file", "_source_file"),
            ("file_name", "_file_name"),
            ("filename", "_file_name"),
            ("original_filename", "_file_name"),
            ("assay_name", "_assay_name"),
            ("assay_id", "_assay_id"),
        ):
            val = metadata.get(meta_key)
            if val is not None and str(val).strip() and row_key not in row:
                row[row_key] = str(val).strip()
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
    if _is_inchikey_validity_query(q):
        return True
    if _is_multi_assay_inactive_query(q):
        return True
    if _is_panel_observation_query(q):
        return True
    if _is_max_assays_per_compound_query(q):
        return True
    if _is_compound_inventory_query(q):
        return True
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


_INCHIKEY_FORMAT_RE = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")


def _is_inchikey_validity_query(query: str) -> bool:
    q = str(query or "").strip().lower()
    if not re.search(r"\binchi[\s_-]*keys?\b", q):
        return False
    return bool(
        re.search(
            r"\b(invalid|valid|rejected|reject|malformed|bad|missing|blank|empty|format|well[- ]?formed)\b",
            q,
        )
    )


def _pick_inchikey_field(columns: Sequence[str]) -> Optional[str]:
    preferred = (
        "PUBCHEM_IUPAC_INCHIKEY",
        "INCHIKEY",
        "InChIKey",
        "inchikey",
        "INCHI_KEY",
        "compound_id",  # Mongo chemical fabric observations
        "InChIKeys",
        "_id",  # compounds master collection on Mongo fabric
    )
    lower_map = {str(c).lower().replace(" ", "_"): c for c in columns}
    for pref in preferred:
        key = pref.lower().replace(" ", "_")
        if key in lower_map:
            return lower_map[key]
    for col in columns:
        cl = str(col).lower()
        if "inchi" in cl or cl in {"compound_id", "compoundid"}:
            return col
    return None


def _row_compound_key(row: Dict[str, str]) -> Optional[str]:
    """Best InChIKey / compound identifier on a row (master or observation)."""
    for field in (
        "inchikey",
        "InChIKey",
        "INCHIKEY",
        "PUBCHEM_IUPAC_INCHIKEY",
        "compound_id",
        "InChIKeys",
        "_id",
    ):
        raw = str(row.get(field, "")).strip()
        if not raw or raw.lower() in {"none", "null", "nan"}:
            continue
        upper = raw.upper()
        if _INCHIKEY_FORMAT_RE.match(upper):
            return upper
        if raw.isdigit() and field.upper() in {"CID", "PUBCHEM_CID", "_ID"}:
            return raw
    # any inchi-ish column
    for key, val in row.items():
        if "inchi" not in str(key).lower() and str(key).lower() not in {"compound_id", "_id"}:
            continue
        raw = str(val or "").strip()
        if raw and _INCHIKEY_FORMAT_RE.match(raw.upper()):
            return raw.upper()
    return None


def _is_compound_master_row(row: Dict[str, str]) -> bool:
    """True for compounds-collection rows (no assay dataset_id; has structure/coverage)."""
    if str(row.get("dataset_id", "")).strip() or str(row.get("assay_id", "")).strip():
        return False
    if not _row_compound_key(row):
        return False
    # Positive signals from Mongo compounds master
    if any(
        str(row.get(k, "")).strip()
        for k in (
            "connectivity_key",
            "data_coverage",
            "structure",
            "structure.canonical_smiles",
            "datasets",
            "inchikey",
        )
    ):
        return True
    # Master-like: has InChIKey _id and no observation outcome
    if str(row.get("_id", "")).strip() and not str(row.get("outcome", "")).strip():
        return True
    return False


def _is_compound_inventory_query(query: str) -> bool:
    """How many chemical compounds / molecules are in the fabric/database."""
    q = str(query or "").strip().lower()
    if not re.search(r"\b(how many|count|number of|total|present)\b", q):
        return False
    if not re.search(r"\b((chemical\s+)?compounds?|molecules?|structures?)\b", q):
        return False
    # Observations / panels / inactive intersection — other handlers.
    if re.search(
        r"\b(observations?|assays?|inactive|across|cyp[\s_-]*\d|her2|pampa|rlm|solubility|per\s+compound)\b",
        q,
    ):
        return False
    if re.search(r"\binvalid\b|\brejected\b|\bmalformed\b|\bmaximum\b|\bmax\b", q):
        return False
    return True


def analyze_compound_inventory(
    rows: Sequence[Dict[str, str]],
    *,
    fabric_name: str = "knowledge fabric",
) -> Optional[Dict[str, Any]]:
    """Count unique chemical compounds (prefer compounds-master rows)."""
    if not rows:
        return None

    master_keys: set = set()
    obs_keys: set = set()
    all_keys: set = set()
    master_rows = 0
    obs_rows = 0

    for row in rows:
        key = _row_compound_key(row)
        if not key:
            continue
        all_keys.add(key)
        if _is_compound_master_row(row):
            master_keys.add(key)
            master_rows += 1
        elif str(row.get("dataset_id", "")).strip() or str(row.get("assay_id", "")).strip():
            obs_keys.add(key)
            obs_rows += 1
        else:
            # Unclassified row with an InChIKey — count toward all_keys only
            pass

    # Prefer master inventory when present; else distinct keys anywhere
    if master_keys:
        primary = len(master_keys)
        primary_label = "Compounds (master collection)"
        source = "master"
    else:
        primary = len(all_keys)
        primary_label = "Distinct InChIKeys / compound IDs"
        source = "distinct_all"

    table = [
        [primary_label, primary],
        ["Distinct compounds in assay observations", len(obs_keys)],
        ["Indexed rows scanned", len(rows)],
        ["Compound-master rows", master_rows],
        ["Assay observation rows (with compound id)", obs_rows],
    ]

    answer = "\n".join(
        [
            f"## Chemical compounds — **{fabric_name}**",
            "",
            markdown_table(["Metric", "Count"], table),
            "",
            f"**Answer:** **{primary:,}** chemical compounds "
            + (
                "in the compounds master collection."
                if source == "master"
                else "by distinct InChIKey / compound ID across indexed rows."
            ),
            "",
            "### Notes",
            "- Master count uses compound rows (`inchikey` / `_id`) without an assay `dataset_id`.",
            "- Observation distinct count can be lower when not every master compound has measured assays.",
            "- This is **not** the total fabric chunk count (observations + compounds + assays).",
        ]
    )
    return {
        "intent": "compound_inventory",
        "row_total": len(rows),
        "answer": answer,
        "metrics": {
            "compounds": primary,
            "master_distinct": len(master_keys),
            "observation_distinct": len(obs_keys),
            "all_distinct": len(all_keys),
            "master_rows": master_rows,
            "observation_rows": obs_rows,
            "source": source,
        },
    }


def _is_max_assays_per_compound_query(query: str) -> bool:
    """Max / distribution of distinct assays (or panels) per compound."""
    q = str(query or "").strip().lower()
    if not re.search(r"\b(assay|assays|panel|panels|dataset)\b", q):
        return False
    if not re.search(r"\b(compound|compounds|molecule|molecules|per\s+compound)\b", q):
        return False
    return bool(
        re.search(
            r"\b(max(?:imum)?|most|highest|how many.+per|per\s+compound|distribution|coverage)\b",
            q,
        )
        or re.search(r"assays?\s+per\s+compounds?", q)
        or re.search(r"compounds?\s+with\s+(?:the\s+)?most\s+assays?", q)
    )


def analyze_max_assays_per_compound(
    rows: Sequence[Dict[str, str]],
    *,
    fabric_name: str = "knowledge fabric",
) -> Optional[Dict[str, Any]]:
    """Find max distinct assays/panels per compound and how many compounds hit that max."""
    if not rows:
        return None

    by_dataset: Dict[str, set] = defaultdict(set)
    by_assay: Dict[str, set] = defaultdict(set)

    for row in rows:
        key = _row_compound_key(row)
        if not key:
            # observation rows may only have compound_id
            key = str(row.get("compound_id", "")).strip().upper()
            if not key or not _INCHIKEY_FORMAT_RE.match(key):
                continue
        ds = str(row.get("dataset_id", "")).strip()
        aid = str(row.get("assay_id", "")).strip()
        if ds:
            by_dataset[key].add(ds)
        if aid:
            by_assay[key].add(aid)

    if not by_dataset and not by_assay:
        return {
            "intent": "max_assays_per_compound",
            "row_total": len(rows),
            "answer": "\n".join(
                [
                    f"## Assays per compound — **{fabric_name}**",
                    "",
                    "No rows with both a compound ID and `dataset_id` / `assay_id` were found.",
                ]
            ),
            "metrics": {"max": 0, "compounds_at_max": 0},
        }

    # Prefer assay_id when present; fall back to dataset_id (panels).
    use_assay = sum(1 for s in by_assay.values() if s) >= sum(1 for s in by_dataset.values() if s) * 0.8
    primary = by_assay if use_assay else by_dataset
    grain = "assay_id" if use_assay else "dataset_id"
    grain_label = "distinct assays (`assay_id`)" if use_assay else "distinct panels (`dataset_id`)"

    hist: Counter = Counter(len(s) for s in primary.values() if s)
    max_n = max(hist) if hist else 0
    at_max = hist.get(max_n, 0)
    examples = sorted([cid for cid, s in primary.items() if len(s) == max_n])[:12]
    example_panels = sorted(primary[examples[0]]) if examples else []

    dist_rows = [[n, hist[n]] for n in sorted(hist)]
    answer = "\n".join(
        [
            f"## Assays per compound — **{fabric_name}**",
            "",
            f"Counted **{grain_label}** per compound across assay observation rows.",
            "",
            markdown_table(
                ["Metric", "Value"],
                [
                    [f"Maximum {grain_label}", max_n],
                    ["Compounds at that maximum", at_max],
                    ["Compounds with ≥1 assay/panel", len(primary)],
                    ["Indexed rows scanned", len(rows)],
                ],
            ),
            "",
            f"**Answer:** Max = **{max_n}** {grain.replace('_', ' ')}s per compound; "
            f"**{at_max:,}** compound{'s' if at_max != 1 else ''} reach that maximum.",
            "",
            "### Distribution",
            "",
            markdown_table([f"{grain} count", "Compounds"], dist_rows),
            "",
            "### Example compounds at the maximum"
            if examples
            else "### Examples",
            "",
            (
                markdown_table(
                    ["InChIKey / compound_id", grain],
                    [[cid, ", ".join(sorted(primary[cid]))] for cid in examples],
                )
                if examples
                else "_None._"
            ),
            "",
            "### Notes",
            f"- Grain: `{grain}`"
            + (f" (e.g. {', '.join(example_panels)})." if example_panels else "."),
            "- Duplicate observation rows for the same compound × assay count once.",
            "- Compounds present only in the master collection (no assay rows) are excluded.",
        ]
    )
    return {
        "intent": "max_assays_per_compound",
        "row_total": len(rows),
        "answer": answer,
        "metrics": {
            "max": max_n,
            "compounds_at_max": at_max,
            "compounds_with_assays": len(primary),
            "distribution": dict(hist),
            "grain": grain,
            "examples": examples,
        },
    }


def _classify_inchikey_value(raw: Any) -> str:
    s = "" if raw is None else str(raw).strip()
    if not s or s.lower() in {"n/a", "na", "null", "none", "nan", "-", "error", "failed", "invalid", "unknown"}:
        return "blank"
    if _INCHIKEY_FORMAT_RE.match(s.upper()):
        return "valid"
    return "invalid"


def analyze_inchikey_validity(
    rows: Sequence[Dict[str, str]],
    *,
    fabric_name: str = "knowledge fabric",
) -> Optional[Dict[str, Any]]:
    """Count valid vs invalid InChIKeys by standard 14-10-1 format over all rows."""
    if not rows:
        return None
    columns = _columns(rows)
    field = _pick_inchikey_field(columns)
    if not field:
        return {
            "intent": "inchikey_format_validity",
            "row_total": len(rows),
            "answer": "\n".join(
                [
                    f"## InChIKey format validity — **{fabric_name}**",
                    "",
                    "No InChIKey-like column was found on this fabric.",
                    "",
                    "Candidate columns:",
                    "",
                    markdown_table(["Column"], [[c] for c in list(columns)[:30]] or [["(none)"]]),
                ]
            ),
            "metrics": {"row_total": len(rows), "field": None},
        }

    valid = invalid = blank = 0
    invalid_examples: List[str] = []
    for row in rows:
        status = _classify_inchikey_value(row.get(field))
        if status == "valid":
            valid += 1
        elif status == "blank":
            blank += 1
        else:
            invalid += 1
            val = str(row.get(field, "")).strip()
            if val and val not in invalid_examples and len(invalid_examples) < 12:
                invalid_examples.append(val)

    total = len(rows)
    rejected = invalid + blank

    def pct(n: int) -> str:
        return f"{(100.0 * n / total):.2f}" if total else "0.00"

    example_lines: List[str] = []
    if invalid_examples:
        example_lines = [
            "",
            "### Example invalid / non-standard values",
            "",
            markdown_table(["Value"], [[v] for v in invalid_examples]),
        ]
    else:
        example_lines = ["", "_No malformed (non-blank) InChIKey strings were found._"]

    answer = "\n".join(
        [
            f"## InChIKey format validity — **{fabric_name}**",
            "",
            f"Column: `{field}`. Valid = standard shape `XXXXXXXXXXXXXX-XXXXXXXXXX-X` (14-10-1 letters).",
            "Blank/missing and malformed strings count as **rejected** for this check.",
            "",
            markdown_table(
                ["Status", "Count", "% of rows"],
                [
                    ["Valid InChIKeys", valid, f"{pct(valid)}%"],
                    ["Invalid / malformed", invalid, f"{pct(invalid)}%"],
                    ["Blank / missing", blank, f"{pct(blank)}%"],
                    ["**Rejected (invalid + blank)**", f"**{rejected}**", f"**{pct(rejected)}%**"],
                    ["Total rows", total, "100%"],
                ],
            ),
            "",
            f"**Answer:** **{rejected:,}** InChIKeys were rejected by format checks "
            f"(**{invalid:,}** malformed + **{blank:,}** blank/missing) out of **{total:,}** rows.",
            *example_lines,
            "",
            "### Notes",
            f"- Computed over **all {total:,} indexed row chunks** in Weave (full fabric).",
            "- Structural format only — not ChemSpider/NIH chemistry validation.",
        ]
    )
    return {
        "intent": "inchikey_format_validity",
        "row_total": total,
        "field": field,
        "answer": answer,
        "metrics": {
            "field": field,
            "valid": valid,
            "invalid": invalid,
            "blank": blank,
            "rejected": rejected,
            "row_total": total,
        },
    }


# Panel / CYP / multi-assay -----------------------------------------------
# Canonical panel name → match patterns against dataset_id / assay_id / source text.
_PANEL_PATTERNS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("CYP2C9", (r"cyp[\s_-]*2c9", r"(?<![a-z0-9])2c9(?![a-z0-9])")),
    ("CYP2D6", (r"cyp[\s_-]*2d6", r"(?<![a-z0-9])2d6(?![a-z0-9])")),
    ("CYP3A4", (r"cyp[\s_-]*3a4", r"(?<![a-z0-9])3a4(?![a-z0-9])")),
    ("CYP1A2", (r"cyp[\s_-]*1a2", r"(?<![a-z0-9])1a2(?![a-z0-9])")),
    ("CYP2C19", (r"cyp[\s_-]*2c19", r"(?<![a-z0-9])2c19(?![a-z0-9])")),
    ("HER2", (r"her[\s_-]*2", r"her2_activity")),
    ("RLM", (r"(?<![a-z0-9])rlm(?![a-z0-9])", r"rlm_stability", r"microsomal")),
    ("PAMPA_PH7", (r"pampa[\s_-]*ph[\s_-]*7", r"pampa_ph7")),
    ("PAMPA_PH5", (r"pampa[\s_-]*ph[\s_-]*5", r"pampa_ph5")),
    ("PAMPA", (r"(?<![a-z0-9])pampa(?![a-z0-9])",)),
    ("SOLUBILITY", (r"solubility", r"kinetic_solubility")),
)

_CYP_ASSAY_PATTERNS = tuple(p for p in _PANEL_PATTERNS if p[0].startswith("CYP"))


def _is_multi_assay_inactive_query(query: str) -> bool:
    q = str(query or "").strip().lower()
    if not re.search(r"\binactive\b", q):
        return False
    assays = _extract_assays_from_query(q)
    if len(assays) >= 2:
        return True
    return bool(re.search(r"\b(across|all\s+three|union|intersection|common)\b", q) and "cyp" in q)


def _extract_assays_from_query(query: str) -> List[str]:
    """CYP assays named in the query (subset of panel extractor)."""
    return [p for p in _extract_panels_from_query(query) if p.startswith("CYP")]


def _extract_panels_from_query(query: str) -> List[str]:
    q = str(query or "")
    found: List[str] = []
    for name, patterns in _PANEL_PATTERNS:
        if name == "PAMPA":
            # Prefer specific pH panels when they also match; keep generic PAMPA as a rollup request.
            if any(re.search(p, q, flags=re.IGNORECASE) for p in patterns):
                found.append(name)
            continue
        if any(re.search(p, q, flags=re.IGNORECASE) for p in patterns):
            found.append(name)
    return found


def _row_panel_blob(row: Dict[str, str]) -> str:
    parts = [
        str(row.get("dataset_id", "")),
        str(row.get("assay_id", "")),
        str(row.get("_source_name", "")),
        str(row.get("_source_file", "")),
        str(row.get("_file_name", "")),
        str(row.get("_assay_name", "")),
        str(row.get("_assay_id", "")),
        str(row.get("PUBCHEM_ACTIVITY_URL", "")),
        str(row.get("ASSAY", "")),
        str(row.get("assay", "")),
        str(row.get("source_name", "")),
        str(row.get("file_name", "")),
        str(row.get("provenance.source_file", "")),
    ]
    return " ".join(parts)


def _row_assay_label(row: Dict[str, str]) -> Optional[str]:
    """Return the CYP assay tag for a row (used by multi-assay Inactive)."""
    ds = str(row.get("dataset_id", "")).strip().upper()
    if ds:
        for name, _patterns in _CYP_ASSAY_PATTERNS:
            if name in ds:
                return name
    blob = _row_panel_blob(row)
    for name, patterns in _CYP_ASSAY_PATTERNS:
        if any(re.search(p, blob, flags=re.IGNORECASE) for p in patterns):
            return name
    return None


def _row_panel_labels(row: Dict[str, str]) -> List[str]:
    """All panel tags that apply to a row (e.g. PAMPA_PH7 also counts as PAMPA)."""
    blob = _row_panel_blob(row)
    ds = str(row.get("dataset_id", "")).strip().upper()
    labels: List[str] = []
    for name, patterns in _PANEL_PATTERNS:
        if name == "PAMPA":
            continue
        hit = False
        if ds and (ds == name or name in ds):
            hit = True
        elif any(re.search(p, blob, flags=re.IGNORECASE) for p in patterns):
            hit = True
        if hit:
            labels.append(name)
    # Roll PAMPA_* into generic PAMPA
    pampa_patterns = dict(_PANEL_PATTERNS).get("PAMPA", ())
    if (
        any(l.startswith("PAMPA_") for l in labels)
        or (ds.startswith("PAMPA") if ds else False)
        or any(re.search(p, blob, flags=re.IGNORECASE) for p in pampa_patterns)
    ):
        if "PAMPA" not in labels:
            labels.append("PAMPA")
    return labels


def _is_panel_observation_query(query: str) -> bool:
    q = str(query or "").strip().lower()
    if _is_multi_assay_inactive_query(q):
        return False
    panels = _extract_panels_from_query(q)
    if len(panels) < 1:
        # Still allow "observations by dataset_id / assay"
        if re.search(r"\b(observations?|rows?)\b", q) and re.search(
            r"\b(dataset[_ ]?id|assay[_ ]?id|panel|assay)\b", q
        ):
            return True
        return False
    return bool(
        re.search(
            r"\b(how many|count|counts|number of|observations?|rows?|per)\b",
            q,
        )
        or "/" in q
        or "vs" in q
        or "versus" in q
    )


def _pick_compound_key_field(columns: Sequence[str]) -> Optional[str]:
    for pref in (
        "compound_id",
        "InChIKeys",
        "INCHIKEY",
        "InChIKey",
        "PUBCHEM_IUPAC_INCHIKEY",
        "PUBCHEM_CID",
        "CID",
    ):
        resolved, _ = _resolve_column_fragment(pref, columns)
        if resolved:
            return resolved
        hit = _find_column(pref, columns)
        if hit:
            return hit
    # fallback: any inchi column
    return _pick_inchikey_field(columns)


def _pick_outcome_field(columns: Sequence[str]) -> Optional[str]:
    for pref in (
        "outcome_label",
        "outcome.phenotype",
        "outcome.source_label",
        "outcome.standard_label",
        "PUBCHEM_ACTIVITY_OUTCOME",
        "ACTIVITY_OUTCOME",
        "phenotype",
        "outcome",
    ):
        resolved, _ = _resolve_column_fragment(pref, columns)
        if resolved:
            return resolved
        hit = _find_column(pref, columns)
        if hit:
            return hit
    for col in columns:
        if "outcome" in str(col).lower():
            return col
    return None


def analyze_panel_observation_counts(
    rows: Sequence[Dict[str, str]],
    query: str,
    *,
    fabric_name: str = "knowledge fabric",
) -> Optional[Dict[str, Any]]:
    """Count observations per named panel (dataset_id / assay tag)."""
    if not rows:
        return None
    requested = _extract_panels_from_query(query)
    # Count every panel that appears
    panel_counts: Counter = Counter()
    dataset_counts: Counter = Counter()
    for row in rows:
        ds = str(row.get("dataset_id", "")).strip()
        if ds:
            dataset_counts[ds] += 1
        for label in _row_panel_labels(row):
            panel_counts[label] += 1

    # If user named panels, report those (expand PAMPA → specific pH rows + rollup).
    if requested:
        display: List[Tuple[str, int]] = []
        seen = set()
        for name in requested:
            if name == "PAMPA":
                for specific in ("PAMPA_PH7", "PAMPA_PH5"):
                    if specific not in seen:
                        display.append((specific, int(panel_counts.get(specific, 0))))
                        seen.add(specific)
                if "PAMPA (all)" not in seen:
                    display.append(("PAMPA (all)", int(panel_counts.get("PAMPA", 0))))
                    seen.add("PAMPA (all)")
            else:
                if name not in seen:
                    display.append((name, int(panel_counts.get(name, 0))))
                    seen.add(name)
        table_rows = [[n, c] for n, c in display]
        note_panels = ", ".join(f"`{n}`" for n, _ in display)
    else:
        # Full dataset_id breakdown (prefer raw dataset_id when present)
        if dataset_counts:
            table_rows = [[k, v] for k, v in dataset_counts.most_common()]
            note_panels = "`dataset_id`"
        else:
            table_rows = [[k, v] for k, v in panel_counts.most_common() if k != "PAMPA"]
            note_panels = "inferred panels"

    total_matched = sum(c for _, c in table_rows if not str(_).endswith("(all)"))
    # Avoid double-counting PAMPA (all) in the matched total
    total_matched = 0
    for label, count in table_rows:
        if str(label).endswith("(all)"):
            continue
        total_matched += int(count)

    answer = "\n".join(
        [
            f"## Observation counts by panel — **{fabric_name}**",
            "",
            f"Requested / reported panels: {note_panels}.",
            "",
            markdown_table(["Panel / dataset", "Observations"], table_rows or [["(none)", 0]]),
            "",
            f"**Answer:** **{total_matched:,}** observations across the listed panels "
            f"(from **{len(rows):,}** indexed rows scanned).",
            "",
            "### Notes",
            "- Counts use `dataset_id` / `assay_id` when present (Mongo chemical fabric), "
            "not semantic retrieve.",
            "- `PAMPA (all)` is the rollup of PAMPA_PH5 + PAMPA_PH7 when PAMPA is requested.",
            "- Compound-master rows without a panel tag are excluded from panel totals.",
        ]
    )
    return {
        "intent": "panel_observation_counts",
        "row_total": len(rows),
        "answer": answer,
        "metrics": {
            "requested": requested,
            "panel_counts": dict(panel_counts),
            "dataset_counts": dict(dataset_counts),
            "table": table_rows,
            "matched": total_matched,
        },
    }


def analyze_multi_assay_inactive(
    rows: Sequence[Dict[str, str]],
    query: str,
    *,
    fabric_name: str = "knowledge fabric",
) -> Optional[Dict[str, Any]]:
    """
    Find compounds (by InChIKey/CID) that are Inactive in every requested CYP assay.

    Requires each row to be taggable to an assay via source/file/assay metadata
    (e.g. NCATS_CYP2C9_….xlsx) after ingestion into one fabric.
    """
    if not rows:
        return None
    assays = _extract_assays_from_query(query)
    if len(assays) < 2:
        assays = ["CYP2C9", "CYP2D6", "CYP3A4"]

    columns = _columns(rows)
    key_field = _pick_compound_key_field(columns)
    outcome_field = _pick_outcome_field(columns)
    if not key_field or not outcome_field:
        return {
            "intent": "multi_assay_inactive",
            "row_total": len(rows),
            "answer": "\n".join(
                [
                    f"## Multi-assay Inactive — **{fabric_name}**",
                    "",
                    "Could not find compound key (InChIKey/CID) and/or activity outcome columns.",
                    "",
                    markdown_table(["Column"], [[c] for c in list(columns)[:40]] or [["(none)"]]),
                ]
            ),
            "metrics": {"assays": assays, "key_field": key_field, "outcome_field": outcome_field},
        }

    # compound -> assay -> set(outcomes)
    by_compound: Dict[str, Dict[str, set]] = defaultdict(lambda: defaultdict(set))
    assay_row_counts: Counter = Counter()
    tagged = 0
    for row in rows:
        assay = _row_assay_label(row)
        if not assay or assay not in assays:
            continue
        key = str(row.get(key_field, "")).strip()
        if not key or key.lower() in {"string", "float", "integer", "none"}:
            continue
        if not (_INCHIKEY_FORMAT_RE.match(key.upper()) or key.isdigit()):
            continue
        labels_for_row = {
            str(row.get(outcome_field, "")).strip(),
            str(row.get("outcome.source_label", "")).strip(),
            str(row.get("outcome.standard_label", "")).strip(),
            str(row.get("outcome.phenotype", "")).strip(),
            str(row.get("outcome_label", "")).strip(),
            str(row.get("phenotype", "")).strip(),
        }
        labels_for_row = {
            x
            for x in labels_for_row
            if x
            and x.lower() not in {"none", "null", "nan", "string", "float", "integer"}
            and not x.startswith("{")
        }
        if not labels_for_row:
            continue
        by_compound[key][assay].update(labels_for_row)
        assay_row_counts[assay] += 1
        tagged += 1

    if tagged == 0:
        return {
            "intent": "multi_assay_inactive",
            "row_total": len(rows),
            "answer": "\n".join(
                [
                    f"## Multi-assay Inactive — **{fabric_name}**",
                    "",
                    f"Looking for Inactive across: {', '.join(f'`{a}`' for a in assays)}.",
                    "",
                    "No rows could be tagged to those assays. Rows need `dataset_id` / `assay_id` "
                    "(e.g. `CYP2C9`) or assay names in the **source/file name**.",
                    "",
                    f"Scanned **{len(rows):,}** rows; compound key=`{key_field}`, outcome=`{outcome_field}`.",
                ]
            ),
            "metrics": {
                "assays": assays,
                "tagged_rows": 0,
                "key_field": key_field,
                "outcome_field": outcome_field,
            },
        }

    inactive_hits: List[str] = []
    for key, assay_map in by_compound.items():
        if not all(a in assay_map for a in assays):
            continue
        if all(
            any(o.lower() == "inactive" for o in assay_map[a])
            and not any(o.lower() == "active" for o in assay_map[a])
            for a in assays
        ):
            # Prefer clear Inactive (allow Inactive-only even if also Inconclusive? user asked inactive)
            # Require at least one Inactive per assay; disallow Active on any required assay.
            inactive_hits.append(key)

    inactive_hits.sort()
    preview = inactive_hits[:40]
    assay_count_rows = [[a, assay_row_counts.get(a, 0)] for a in assays]

    answer = "\n".join(
        [
            f"## Compounds Inactive across {', '.join(assays)} — **{fabric_name}**",
            "",
            f"Compound key: `{key_field}` · Outcome: `{outcome_field}`.",
            "A compound is counted only if it appears in **all** listed assays and is **Inactive** "
            "(no **Active** outcome) on each.",
            "",
            markdown_table(["Assay", "Tagged rows"], assay_count_rows),
            "",
            f"**Answer:** **{len(inactive_hits):,}** compounds are Inactive across "
            f"{', '.join(assays)} "
            f"(out of **{len(by_compound):,}** compounds seen in ≥1 of these assays).",
            "",
            "### Example Inactive compounds"
            if preview
            else "### Examples",
            "",
            markdown_table([key_field], [[k] for k in preview])
            if preview
            else "_No compounds matched Inactive on all requested assays._",
            "",
            "### Notes",
            f"- Deterministic full-fabric scan over **{len(rows):,}** rows "
            f"(**{tagged:,}** rows tagged to requested assays).",
            "- Assay membership inferred from source/file/assay metadata (e.g. `NCATS_CYP2C9_…`).",
            "- This is **not** semantic retrieve; HER2/other panels are ignored unless named.",
        ]
    )
    return {
        "intent": "multi_assay_inactive",
        "row_total": len(rows),
        "field": key_field,
        "answer": answer,
        "metrics": {
            "assays": assays,
            "inactive_count": len(inactive_hits),
            "compounds_seen": len(by_compound),
            "tagged_rows": tagged,
            "key_field": key_field,
            "outcome_field": outcome_field,
            "assay_row_counts": dict(assay_row_counts),
            "examples": preview,
        },
    }


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
        "row", "rows", "record", "records",
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

    # Multi-assay Inactive intersection (e.g. CYP2C9 ∩ CYP2D6 ∩ CYP3A4).
    if _is_multi_assay_inactive_query(query):
        result = analyze_multi_assay_inactive(filtered_rows or rows, query, fabric_name=fabric_name)
        if result is not None:
            result["filters"] = filters
            return result

    # Max distinct assays / panels per compound (before compound inventory —
    # questions like "number of assays per compound" must not count as inventory).
    if _is_max_assays_per_compound_query(query):
        result = analyze_max_assays_per_compound(filtered_rows or rows, fabric_name=fabric_name)
        if result is not None:
            result["filters"] = filters
            return result

    # Chemical compound inventory (unique compounds in database / fabric).
    if _is_compound_inventory_query(query):
        result = analyze_compound_inventory(filtered_rows or rows, fabric_name=fabric_name)
        if result is not None:
            result["filters"] = filters
            return result

    # Panel / dataset observation counts (CYP2C9, HER2, RLM, PAMPA, …).
    if _is_panel_observation_query(query):
        result = analyze_panel_observation_counts(
            filtered_rows or rows, query, fabric_name=fabric_name
        )
        if result is not None:
            result["filters"] = filters
            return result

    # InChIKey structural validity (invalid / rejected / blank) over full fabric rows.
    if _is_inchikey_validity_query(query):
        result = analyze_inchikey_validity(filtered_rows or rows, fabric_name=fabric_name)
        if result is not None:
            result["filters"] = filters
            return result

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
