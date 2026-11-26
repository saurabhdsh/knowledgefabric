"""Answer questions about tabular fabrics from the table store (Release 2.0, Phase 1).

* ``find_entities`` — exact lookup of identifiers / names mentioned in a
  question, expanded to parent and child rows through the profiled foreign keys.
* ``answer_with_sql`` — the LLM writes one SELECT, the store runs it read-only
  over all rows, and the answer is written from the result. The SQL and the
  result are returned so every number can be checked.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.services.fabric_pipeline.table_store import SqlNotAllowedError, TableStore, TableStoreError
from app.services.fabric_pipeline.tabular_index import _fmt, _humanize, _singular_label, sql_schema_text
from app.services.fabric_pipeline.tabular_profiler import _MONEY_NAME_RE, table_by_name

logger = logging.getLogger(__name__)

# (messages, max_tokens, temperature) -> completion text
LLMCall = Callable[[List[Dict[str, str]], int, float], str]

_ID_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./\-]*[A-Za-z0-9]|[0-9]")
_QUOTED_RE = re.compile(r"[\"“]([^\"”]{2,80})[\"”]")
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’.&\-]*")
_STOPWORDS = {
    "a", "an", "the", "of", "for", "to", "in", "on", "at", "by", "and", "or", "is", "are", "was", "were",
    "what", "which", "who", "whom", "how", "why", "when", "where", "tell", "me", "about", "please", "show",
    "give", "list", "find", "get", "all", "any", "with", "from", "that", "this", "these", "those", "does",
    "do", "did", "has", "have", "had", "summarise", "summarize", "summary", "explain", "describe", "details",
    "many", "much", "total", "top", "it", "its", "their", "his", "her", "my", "our", "you", "your", "be", "been",
}
MAX_NAME_NGRAM = 4

_STRUCTURED_RE = re.compile(
    r"\b(how many|how much|count|number of|total|sum|average|avg|mean|median|minimum|maximum|"
    r"min|max|top\s+\d+|top|bottom|highest|lowest|most|least|largest|smallest|greater than|"
    r"less than|more than|fewer than|at least|at most|between|per|by each|group|breakdown|"
    r"distribution|percent|percentage|ratio|rate|share|rank|list all|list the|which|who has|"
    r"compare|trend|over time|monthly|yearly|distinct|unique|duplicates?)\b",
    re.I,
)

MAX_CHILD_ROWS = 15
MAX_ENTITIES = 4


def looks_structured(query: str, profile: Dict[str, Any]) -> bool:
    """Whether a question is likely answered by computing over rows."""
    if _STRUCTURED_RE.search(query or ""):
        return True
    lowered = (query or "").lower()
    for table in profile.get("tables", []):
        for col in table["columns"]:
            if col["role"] in ("measure",) and _humanize(col["name"]).lower() in lowered:
                return True
    return False


def _id_aliases(token: str) -> List[str]:
    """Expand common demo/agent ID spellings (underscore vs hyphen, zero-pad, MBR→MEM)."""
    raw = (token or "").strip()
    if not raw:
        return []
    out: List[str] = []
    seen = set()

    def add(value: str) -> None:
        if value and value not in seen:
            seen.add(value)
            out.append(value)

    add(raw)
    if "_" in raw:
        add(raw.replace("_", "-"))
    if "-" in raw:
        add(raw.replace("-", "_"))

    for candidate in list(out):
        m = re.match(r"^([A-Za-z]+)[-_](\d+)$", candidate)
        if not m:
            continue
        prefix, digits = m.group(1), m.group(2)
        prefixes = [prefix, prefix.upper()]
        if prefix.upper() == "MBR":
            prefixes.extend(["MEM", "mem"])
        if prefix.upper() == "MEM":
            prefixes.append("MBR")
        for pref in prefixes:
            add(f"{pref}-{digits}")
            add(f"{pref}_{digits}")
            for width in (4, 6):
                padded = digits.zfill(width)
                add(f"{pref}-{padded}")
                add(f"{pref}_{padded}")
    return out


def _candidate_tokens(query: str) -> Tuple[List[str], List[str]]:
    """``(identifier-like tokens, name-like phrases)`` found in a question."""
    ids: List[str] = []
    for token in _ID_TOKEN_RE.findall(query or ""):
        token = token.strip(".,;:!?()[]{}")
        if not token:
            continue
        has_digit = any(ch.isdigit() for ch in token)
        coded = bool(re.search(r"[-_]", token)) and token.upper() == token and len(token) >= 4
        if not (has_digit or coded):
            continue
        for alias in _id_aliases(token):
            if alias not in ids:
                ids.append(alias)
    # Name candidates: quoted phrases, then every run of 1-4 consecutive words
    # (longest first). They are only ever matched exactly against label columns.
    names: List[str] = [p.strip() for p in _QUOTED_RE.findall(query or "") if p.strip()]
    words = [w.strip(".,'’") for w in _WORD_RE.findall(query or "")]
    words = [w for w in words if w]
    for size in range(min(MAX_NAME_NGRAM, len(words)), 0, -1):
        for start in range(0, len(words) - size + 1):
            gram = words[start:start + size]
            if gram[0].lower() in _STOPWORDS or gram[-1].lower() in _STOPWORDS:
                continue
            if size == 1 and (len(gram[0]) < 4 or gram[0].isdigit()):
                continue
            phrase = " ".join(gram)
            if phrase not in names:
                names.append(phrase)
    return ids[:16], names[:60]


def _row_dict(table: Dict[str, Any], columns: List[str], row: List[Any]) -> Dict[str, Any]:
    by_sql = {c["sql_name"]: c for c in table["columns"]}
    out: Dict[str, Any] = {}
    for sql_name, value in zip(columns, row):
        col = by_sql.get(sql_name)
        if col is None:
            continue
        if col["type"] == "boolean" and value is not None:
            value = bool(value)
        out[col["name"]] = value
    return out


def _col(table: Dict[str, Any], name: str) -> Dict[str, Any]:
    return next(c for c in table["columns"] if c["name"] == name)


# How sure a lookup is, by the kind of evidence behind it. An identifier is
# exact. A name is weaker: two people can share one, so a name that matches
# several rows is not a match until a second fact picks one of them.
CONFIDENCE_IDENTIFIER = 1.0
CONFIDENCE_NAME_AND_FACT = 0.9
CONFIDENCE_UNIQUE_NAME = 0.8
CONFIDENCE_AMBIGUOUS_NAME = 0.4
MAX_NAME_ROWS = 25

_MONTHS = (
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
)
_NAME_JOINERS = {"of", "and", "the", "de", "la", "van", "von", "del", "da", "di", "for", "&"}


def _date_variants(iso: str) -> List[str]:
    """Ways a stored ISO date is commonly written in a document."""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", str(iso))
    if not m:
        return []
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return []
    month = _MONTHS[mo - 1]
    return [
        f"{y:04d}-{mo:02d}-{d:02d}",
        f"{mo:02d}/{d:02d}/{y:04d}", f"{mo}/{d}/{y:04d}",
        f"{mo:02d}-{d:02d}-{y:04d}",
        f"{month} {d}, {y}", f"{month} {d} {y}", f"{d} {month} {y}",
        f"{month[:3]} {d}, {y}", f"{month[:3]} {d} {y}", f"{d} {month[:3]} {y}",
    ]


def _second_fact(table: Dict[str, Any], row: Dict[str, Any], label: str, text: str) -> Optional[str]:
    """A column, other than the name, whose value for this row is also in the text.

    Only specific values count: a date (birth date, service date) or a value
    that carries digits and is at least five characters long (an identifier, a
    phone number). A plan name or a city is shared by many rows and proves nothing.
    """
    lowered = (text or "").lower()
    for col in table["columns"]:
        if col["name"] == label:
            continue
        value = row.get(col["name"])
        if value is None or value == "" or isinstance(value, bool):
            continue
        if col["type"] in ("date", "datetime"):
            if any(v in lowered for v in _date_variants(str(value))):
                return col["name"]
            continue
        token = str(value).strip().lower()
        if len(token) >= 5 and any(ch.isdigit() for ch in token):
            if re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", lowered):
                return col["name"]
    return None


def _written_as_a_name(phrase: str, text: str) -> bool:
    """Whether ``phrase`` appears in running text the way a proper name does.

    "Lisa Chen" and "Hope Clinic" qualify. The word "hope" in "we hope the
    member" does not, and neither does a single word that is capitalised only
    because it opens a sentence.
    """
    words = phrase.split()
    if not words:
        return False
    for word in words:
        if word.lower() in _NAME_JOINERS and len(words) > 1:
            continue
        if not (word[0].isupper() or word[0].isdigit()):
            return False
    if len(words) > 1 or (words[0].isupper() and len(words[0]) > 1) or any(ch.isdigit() for ch in words[0]):
        return True
    for m in re.finditer(rf"(?<![A-Za-z0-9]){re.escape(words[0])}(?![A-Za-z0-9])", text or ""):
        lead = text[:m.start()]
        before = lead.rstrip()
        if before and "\n" not in lead[len(before):] and before[-1] not in ".!?:;\"“(":
            return True
    return False


def find_entities(
    fabric_id: str,
    profile: Dict[str, Any],
    query: str,
    store: TableStore,
    *,
    max_entities: int = MAX_ENTITIES,
    max_child_rows: int = MAX_CHILD_ROWS,
    strict_names: bool = False,
    ambiguous_names: str = "flag",
    ambiguous_out: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Rows whose key or label is mentioned in the text, with related rows.

    Every match carries ``basis`` and ``confidence``:

    * ``identifier`` (1.0) - a key value appears in the text.
    * ``unique_name`` (0.8) - a name appears and exactly one row has it.
    * ``name_and_second_fact`` (0.9) - several rows share the name and one of
      them also has a date or identifier that appears in the text.
    * ``ambiguous_name`` (0.4) - several rows share the name and nothing in the
      text picks one. With ``ambiguous_names="flag"`` (a user's question) every
      such row is returned, marked. With ``"skip"`` (linking a document
      passage to a row) none is returned.

    ``strict_names`` is for document text: a phrase counts as a name only when
    it is written as one, so the verb in "we hope the member" is not a provider
    called Hope.
    """
    id_tokens, name_phrases = _candidate_tokens(query)
    if strict_names:
        quoted = {p.strip() for p in _QUOTED_RE.findall(query or "")}
        name_phrases = [p for p in name_phrases if p in quoted or _written_as_a_name(p, query or "")]
    if not id_tokens and not name_phrases:
        return []
    lowered_query = (query or "").lower()
    matches: List[Dict[str, Any]] = []
    seen: set = set()

    def _ident(table: Dict[str, Any], data: Dict[str, Any], row: List[Any]) -> Tuple[Any, ...]:
        pk = table["primary_key"]
        return (table["name"], tuple(str(data.get(k)) for k in pk) if pk else tuple(str(v) for v in row))

    def _add(
        table: Dict[str, Any], column: str, columns: List[str], row: List[Any], matched: str,
        *, basis: str = "identifier", confidence: float = CONFIDENCE_IDENTIFIER, **extra: Any,
    ) -> None:
        data = _row_dict(table, columns, row)
        ident = _ident(table, data, row)
        if ident in seen or len(matches) >= max_entities:
            return
        seen.add(ident)
        matches.append({
            "table": table["name"], "matched_column": column, "matched_value": matched, "row": data,
            "basis": basis, "confidence": confidence, **extra,
        })

    # name (lower-case) -> every row, in any table, that carries it
    name_hits: Dict[str, List[Tuple[Dict[str, Any], str, List[str], List[Any]]]] = {}

    for table in profile.get("tables", []):
        if not table["row_count"]:
            continue
        key_cols = [n for n in table.get("key_candidates", []) if n]
        for token in id_tokens:
            numeric = token.isdigit()
            for key in key_cols:
                col = _col(table, key)
                if numeric and col["type"] == "integer":
                    # A bare number only counts as an id when the question names the table or key.
                    noun = _singular_label(table["name"]).lower()
                    if noun not in lowered_query and _humanize(key).lower() not in lowered_query:
                        continue
                    sql = f'SELECT * FROM "{table["sql_name"]}" WHERE "{col["sql_name"]}" = ? LIMIT 2'
                    params: Tuple[Any, ...] = (int(token),)
                elif col["type"] == "string":
                    sql = f'SELECT * FROM "{table["sql_name"]}" WHERE "{col["sql_name"]}" = ? COLLATE NOCASE LIMIT 2'
                    params = (token,)
                else:
                    continue
                result = store.query(fabric_id, sql, params, max_rows=2)
                for row in result["rows"]:
                    _add(table, key, result["columns"], row, token)
        label = table.get("label_column")
        if label and name_phrases:
            col = _col(table, label)
            marks = ", ".join("?" for _ in name_phrases)
            sql = (
                f'SELECT * FROM "{table["sql_name"]}" WHERE "{col["sql_name"]}" COLLATE NOCASE IN ({marks}) '
                f"LIMIT {MAX_NAME_ROWS}"
            )
            result = store.query(fabric_id, sql, tuple(name_phrases), max_rows=MAX_NAME_ROWS)
            label_index = result["columns"].index(col["sql_name"]) if result["rows"] else 0
            for row in result["rows"]:
                name_hits.setdefault(str(row[label_index]).strip().lower(), []).append(
                    (table, label, result["columns"], row)
                )

    # Longest name first, so "Lisa Chen" wins over a plan called "Chen".
    for name in sorted(name_hits, key=lambda n: -len(n)):
        hits = [
            h for h in name_hits[name]
            if _ident(h[0], _row_dict(h[0], h[2], h[3]), h[3]) not in seen
        ]
        if len(hits) < len(name_hits[name]):
            # An identifier in the text already picked the row this name belongs to.
            continue
        if len(name_hits[name]) == 1:
            table, label, columns, row = hits[0]
            _add(table, label, columns, row, str(_row_dict(table, columns, row).get(label)),
                 basis="unique_name", confidence=CONFIDENCE_UNIQUE_NAME)
            continue
        agreeing = []
        for table, label, columns, row in hits:
            fact = _second_fact(table, _row_dict(table, columns, row), label, query or "")
            if fact:
                agreeing.append((table, label, columns, row, fact))
        if len(agreeing) == 1:
            table, label, columns, row, fact = agreeing[0]
            _add(table, label, columns, row, str(_row_dict(table, columns, row).get(label)),
                 basis="name_and_second_fact", confidence=CONFIDENCE_NAME_AND_FACT, second_fact=fact)
            continue
        if ambiguous_out is not None:
            ambiguous_out.append({
                "name": name,
                "row_count": len(name_hits[name]),
                "tables": sorted({h[0]["name"] for h in name_hits[name]}),
            })
        if ambiguous_names == "flag":
            for table, label, columns, row in hits:
                _add(table, label, columns, row, str(_row_dict(table, columns, row).get(label)),
                     basis="ambiguous_name", confidence=CONFIDENCE_AMBIGUOUS_NAME,
                     ambiguous_count=len(name_hits[name]))

    for match in matches:
        table = table_by_name(profile, match["table"])
        match["parents"] = _parents(fabric_id, profile, table, match["row"], store)
        match["children"] = _children(fabric_id, profile, table, match["row"], store, max_child_rows)
    return matches


def rows_by_reference(
    fabric_id: str,
    profile: Dict[str, Any],
    refs: List[Dict[str, Any]],
    store: TableStore,
    *,
    max_entities: int = MAX_ENTITIES,
    max_child_rows: int = MAX_CHILD_ROWS,
) -> List[Dict[str, Any]]:
    """Fetch the exact rows that stored links point at.

    Each ref is ``{table, column, value}``. A ref is followed only when it
    selects one row, so a link is never widened to everyone who shares a name.
    """
    matches: List[Dict[str, Any]] = []
    seen: set = set()
    for ref in refs:
        if len(matches) >= max_entities:
            break
        table = table_by_name(profile, str(ref.get("table") or ""))
        if not table:
            continue
        col = next((c for c in table["columns"] if c["name"] == ref.get("column")), None)
        if col is None or ref.get("value") in (None, ""):
            continue
        value: Any = ref["value"]
        if col["type"] == "integer":
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
        result = store.query(
            fabric_id,
            f'SELECT * FROM "{table["sql_name"]}" WHERE "{col["sql_name"]}" = ? LIMIT 2',
            (value,),
            max_rows=2,
        )
        if len(result["rows"]) != 1:
            continue
        data = _row_dict(table, result["columns"], result["rows"][0])
        ident = (table["name"], tuple(str(v) for v in result["rows"][0]))
        if ident in seen:
            continue
        seen.add(ident)
        matches.append({
            "table": table["name"], "matched_column": col["name"], "matched_value": str(ref["value"]),
            "row": data, "basis": str(ref.get("basis") or "identifier"),
            "confidence": float(ref.get("confidence") or CONFIDENCE_IDENTIFIER),
            "second_fact": ref.get("second_fact"),
        })
    for match in matches:
        table = table_by_name(profile, match["table"])
        match["parents"] = _parents(fabric_id, profile, table, match["row"], store)
        match["children"] = _children(fabric_id, profile, table, match["row"], store, max_child_rows)
    return matches


def _parents(fabric_id: str, profile: Dict[str, Any], table: Dict[str, Any], row: Dict[str, Any], store: TableStore) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for fk in profile.get("foreign_keys", []):
        if fk["from_table"] != table["name"]:
            continue
        value = row.get(fk["from_column"])
        if value is None:
            continue
        parent = table_by_name(profile, fk["to_table"])
        pcol = _col(parent, fk["to_column"])
        result = store.query(
            fabric_id,
            f'SELECT * FROM "{parent["sql_name"]}" WHERE "{pcol["sql_name"]}" = ? LIMIT 1',
            (value,),
            max_rows=1,
        )
        if result["rows"]:
            out.append({
                "via": fk["from_column"],
                "table": parent["name"],
                "row": _row_dict(parent, result["columns"], result["rows"][0]),
            })
    return out


def _children(
    fabric_id: str,
    profile: Dict[str, Any],
    table: Dict[str, Any],
    row: Dict[str, Any],
    store: TableStore,
    max_rows: int,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for fk in profile.get("foreign_keys", []):
        if fk["to_table"] != table["name"] or fk["from_table"] == table["name"]:
            continue
        value = row.get(fk["to_column"])
        if value is None:
            continue
        child = table_by_name(profile, fk["from_table"])
        ccol = _col(child, fk["from_column"])
        money = [c for c in child["columns"] if c["role"] == "measure" and _MONEY_NAME_RE.search(c["name"])][:3]
        agg_sql = ", ".join(["COUNT(*)"] + [f'SUM("{m["sql_name"]}")' for m in money])
        agg = store.query(
            fabric_id,
            f'SELECT {agg_sql} FROM "{child["sql_name"]}" WHERE "{ccol["sql_name"]}" = ?',
            (value,),
            max_rows=1,
        )["rows"][0]
        total = int(agg[0] or 0)
        if not total:
            continue
        date_col = next((c for c in child["columns"] if c["role"] == "date"), None)
        order = f' ORDER BY "{date_col["sql_name"]}" DESC' if date_col else ""
        rows = store.query(
            fabric_id,
            f'SELECT * FROM "{child["sql_name"]}" WHERE "{ccol["sql_name"]}" = ?{order} LIMIT {int(max_rows)}',
            (value,),
            max_rows=max_rows,
        )
        out.append({
            "table": child["name"],
            "via": fk["from_column"],
            "total": total,
            "sums": {m["name"]: agg[1 + i] for i, m in enumerate(money) if agg[1 + i] is not None},
            "rows": [_row_dict(child, rows["columns"], r) for r in rows["rows"]],
            "ordered_by": date_col["name"] if date_col else None,
        })
    return out


def _row_text(row: Dict[str, Any], skip: Tuple[str, ...] = ()) -> str:
    parts = []
    for key, value in row.items():
        if key in skip or value is None or value == "":
            continue
        if isinstance(value, bool):
            value = "yes" if value else "no"
        parts.append(f"{key}: {_fmt(value) if not isinstance(value, str) else value}")
    return "; ".join(parts)


def entity_context_text(matches: List[Dict[str, Any]]) -> str:
    """Render looked-up rows and their related rows as LLM context."""
    blocks: List[str] = []
    for match in matches:
        basis = match.get("basis") or "identifier"
        if basis == "ambiguous_name":
            how = (
                f"one of {match.get('ambiguous_count', 'several')} rows with this name; "
                "the question does not say which one, so do not treat them as the same record"
            )
        elif basis == "unique_name":
            how = "matched by name; the only row with this name"
        elif basis == "name_and_second_fact":
            how = f"matched by name and {match.get('second_fact')}"
        else:
            how = "exact lookup"
        lines = [
            f"[{match['table']}] row where {match['matched_column']} = {match['matched_value']} ({how})",
            "  " + _row_text(match["row"]),
        ]
        for parent in match.get("parents", []):
            lines.append(f"  -> {parent['table']} (via {parent['via']}): {_row_text(parent['row'])}")
        for child in match.get("children", []):
            head = f"  <- {child['table']} (via {child['via']}): {child['total']} row(s) in total"
            if child["sums"]:
                head += "; " + "; ".join(f"total {k} = {_fmt(float(v))}" for k, v in child["sums"].items())
            lines.append(head)
            shown = len(child["rows"])
            if shown < child["total"]:
                order = f" most recent by {child['ordered_by']}" if child.get("ordered_by") else ""
                lines.append(f"     showing {shown}{order} of {child['total']}:")
            for r in child["rows"]:
                lines.append("     - " + _row_text(r, skip=(child["via"],)))
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


# --------------------------------------------------------------------- SQL

_PLAN_SYSTEM = """You translate a question into ONE SQLite SELECT statement over the tables described below.

Rules:
- Use only the tables and columns listed. Never invent a table, column or value.
- Read-only: a single SELECT (CTEs with WITH are fine). No other statement type.
- Booleans are stored as 1/0. Dates are ISO text (YYYY-MM-DD); compare them as text or use date()/strftime().
- Compare text case-insensitively (COLLATE NOCASE or lower()). Use the listed example values to spell categories.
- Join tables only through the listed relationships.
- For "top N" use ORDER BY with LIMIT N. For "how many" use COUNT. Give result columns readable aliases.
- When the question asks for a list, return the identifying columns and the columns the question mentions, not SELECT *.
- If the question cannot be answered by a query over these tables (for example it asks for advice or an explanation), return sql as null.

Reply with JSON only, no prose and no code fence:
{"sql": "<statement or null>", "explanation": "<one sentence: what the query computes>"}"""

_ANSWER_SYSTEM = """You answer a question using only the result of a SQL query that was run over the complete table data.

Rules:
- Use the numbers exactly as they appear in the result. Do not round unless asked, do not estimate, do not add facts that are not in the result.
- Lead with the direct answer. Use a Markdown table when the result has several rows.
- If the result is empty, say that no rows match and state the condition that was applied.
- If a note says the data is a sample of the source or that the result was truncated, say so in one sentence."""


def _parse_plan(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.S)
        if not match:
            raise ValueError("Planner did not return JSON")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("Planner did not return a JSON object")
    return data


def result_markdown(columns: List[str], rows: List[List[Any]], max_rows: int = 50) -> str:
    if not columns:
        return "(no columns)"
    if not rows:
        return "(no rows)"
    head = "| " + " | ".join(str(c) for c in columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join("" if v is None else str(v).replace("|", "\\|").replace("\n", " ") for v in row) + " |"
        for row in rows[:max_rows]
    ]
    return "\n".join([head, sep] + body)


def answer_with_sql(
    fabric_id: str,
    fabric_name: str,
    profile: Dict[str, Any],
    query: str,
    llm: LLMCall,
    store: TableStore,
    *,
    extra_context: str = "",
    max_attempts: int = 2,
) -> Optional[Dict[str, Any]]:
    """Plan, run and explain one SQL query. ``None`` when the planner declines.

    Raises nothing for planner or SQL problems: after ``max_attempts`` the
    result carries ``error`` and no answer, and the caller falls back.
    """
    schema = sql_schema_text(profile)
    sample_note = ""
    sampled = [t for t in profile["tables"] if t.get("is_sample")]
    if sampled:
        sample_note = "Note: " + "; ".join(
            f"{t['sql_name']} holds {t['row_count']:,} of {t['source_row_count']:,} source rows" for t in sampled
        ) + ". Results describe the imported rows only."

    user = f"Dataset: {fabric_name}\nToday: {date.today().isoformat()}\n\n{schema}\n"
    if sample_note:
        user += f"\n{sample_note}\n"
    if extra_context:
        user += f"\nRows already looked up for identifiers in the question:\n{extra_context}\n"
    user += f"\nQuestion: {query}"
    messages = [{"role": "system", "content": _PLAN_SYSTEM}, {"role": "user", "content": user}]

    attempts: List[Dict[str, Any]] = []
    result: Optional[Dict[str, Any]] = None
    sql = explanation = ""
    for _ in range(max_attempts):
        try:
            plan = _parse_plan(llm(messages, 700, 0.0))
        except Exception as exc:
            attempts.append({"error": f"planner: {exc}"})
            break
        sql = plan.get("sql") or ""
        explanation = str(plan.get("explanation") or "")
        if not sql or str(sql).strip().lower() in ("null", "none"):
            return None
        try:
            result = store.query(fabric_id, str(sql))
            attempts.append({"sql": sql})
            break
        except (SqlNotAllowedError, TableStoreError, Exception) as exc:
            attempts.append({"sql": sql, "error": str(exc)})
            messages = messages + [
                {"role": "assistant", "content": json.dumps({"sql": sql, "explanation": explanation})},
                {"role": "user", "content": f"That statement failed: {exc}. Reply with corrected JSON."},
            ]
    if result is None:
        return {"answer": None, "sql": sql, "error": attempts[-1].get("error") if attempts else "no plan", "attempts": attempts}

    notes: List[str] = []
    if result["truncated"]:
        notes.append(f"The result was cut at {result['row_limit']} rows; more rows match.")
    if sample_note:
        notes.append(sample_note)
    table_md = result_markdown(result["columns"], result["rows"])
    shown_note = ""
    if len(result["rows"]) > 50:
        shown_note = f"\n(first 50 of {len(result['rows'])} returned rows shown)"
    answer_user = (
        f"Question: {query}\n\nSQL that was run:\n{sql}\n\nWhat it computes: {explanation}\n\n"
        f"Result ({len(result['rows'])} row(s)):\n{table_md}{shown_note}\n"
    )
    if notes:
        answer_user += "\n" + "\n".join(notes) + "\n"
    try:
        answer = llm(
            [{"role": "system", "content": _ANSWER_SYSTEM}, {"role": "user", "content": answer_user}],
            900,
            0.0,
        ).strip()
    except Exception as exc:
        logger.warning("SQL answer phrasing failed (%s); returning the raw result", exc)
        answer = ""
    if not answer:
        answer = (explanation + "\n\n" if explanation else "") + table_md
        if notes:
            answer += "\n\n" + "\n".join(notes)

    return {
        "answer": answer,
        "sql": sql,
        "explanation": explanation,
        "columns": result["columns"],
        "rows": result["rows"],
        "row_count": len(result["rows"]),
        "truncated": result["truncated"],
        "is_sample": bool(sampled),
        "attempts": attempts,
    }
