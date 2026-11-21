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


def _candidate_tokens(query: str) -> Tuple[List[str], List[str]]:
    """``(identifier-like tokens, name-like phrases)`` found in a question."""
    ids: List[str] = []
    for token in _ID_TOKEN_RE.findall(query or ""):
        token = token.strip(".,;:!?()[]{}")
        if not token:
            continue
        has_digit = any(ch.isdigit() for ch in token)
        coded = bool(re.search(r"[-_]", token)) and token.upper() == token and len(token) >= 4
        if (has_digit or coded) and token not in ids:
            ids.append(token)
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
    return ids[:8], names[:60]


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


def find_entities(
    fabric_id: str,
    profile: Dict[str, Any],
    query: str,
    store: TableStore,
    *,
    max_entities: int = MAX_ENTITIES,
    max_child_rows: int = MAX_CHILD_ROWS,
) -> List[Dict[str, Any]]:
    """Rows whose key or label is mentioned in the question, with related rows."""
    id_tokens, name_phrases = _candidate_tokens(query)
    if not id_tokens and not name_phrases:
        return []
    lowered_query = (query or "").lower()
    matches: List[Dict[str, Any]] = []
    seen: set = set()

    def _add(table: Dict[str, Any], column: str, columns: List[str], row: List[Any], matched: str) -> None:
        data = _row_dict(table, columns, row)
        pk = table["primary_key"]
        ident = (table["name"], tuple(str(data.get(k)) for k in pk) if pk else tuple(str(v) for v in row))
        if ident in seen or len(matches) >= max_entities:
            return
        seen.add(ident)
        matches.append({"table": table["name"], "matched_column": column, "matched_value": matched, "row": data})

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
                f'SELECT * FROM "{table["sql_name"]}" WHERE "{col["sql_name"]}" COLLATE NOCASE IN ({marks}) LIMIT 6'
            )
            result = store.query(fabric_id, sql, tuple(name_phrases), max_rows=6)
            label_index = result["columns"].index(col["sql_name"]) if result["rows"] else 0
            # Longest matching name first, so "Lisa Chen" wins over a plan called "Chen".
            for row in sorted(result["rows"], key=lambda r: -len(str(r[label_index]))):
                _add(table, label, result["columns"], row, str(row[label_index]))

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
        lines = [
            f"[{match['table']}] row where {match['matched_column']} = {match['matched_value']} (exact lookup)",
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
