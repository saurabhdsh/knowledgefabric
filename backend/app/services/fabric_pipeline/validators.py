"""Validate stage: checks a fabric must pass before it is published.

Each check is ``{check, status: pass|warn|fail, detail}``. Any ``fail`` stops
the build. Checks compare what was stored with what was read (counts, sums)
and run real retrieval probes against the index.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional

from app.services.fabric_pipeline.chunker import split_sentences
from app.services.fabric_pipeline.table_store import TableStore
from app.services.fabric_pipeline.tabular_profiler import is_null, normalize_value
from app.services.vector_service import vector_service

PROBE_TOP_K = 5


def _check(name: str, status: str, detail: str, **extra: Any) -> Dict[str, Any]:
    return {"check": name, "status": status, "detail": detail, **extra}


def failed(checks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [c for c in checks if c["status"] == "fail"]


def index_count_check(fabric_id: str, expected: int) -> Dict[str, Any]:
    actual = vector_service.count_source_documents(fabric_id)
    if actual == expected:
        return _check("index_count", "pass", f"{actual:,} chunks indexed, {expected:,} expected")
    return _check("index_count", "fail", f"{actual:,} chunks indexed but {expected:,} were built")


def _run_probes(fabric_id: str, probes: List[Dict[str, str]]) -> Dict[str, Any]:
    hits = 0
    misses: List[str] = []
    ranker = ""
    for probe in probes:
        results = vector_service.search_similar_chunks(probe["query"], fabric_id, top_k=PROBE_TOP_K)
        ranker = (results[0].get("ranker") if results else "") or ranker
        # Same id, or identical text (repeated content is stored once per position).
        if any(str(r.get("id")) == probe["id"] or r.get("content") == probe.get("content") for r in results):
            hits += 1
        else:
            misses.append(probe["query"][:80])
    return {"hits": hits, "total": len(probes), "ranker": ranker, "misses": misses}


def index_roundtrip_check(fabric_id: str, probes: List[Dict[str, str]]) -> Dict[str, Any]:
    """Search with the full text of known chunks: the index must return each one.

    This proves the stored vectors belong to the stored text and that search
    runs on the embedding index. It must pass.
    """
    if not probes:
        return _check("index_roundtrip", "warn", "No chunk was available for an index round-trip check")
    r = _run_probes(fabric_id, probes)
    detail = f"{r['hits']} of {r['total']} chunks found by their own text in the top {PROBE_TOP_K} ({r['ranker'] or 'no ranker'})"
    if not r["ranker"].startswith("vector:"):
        return _check("index_roundtrip", "fail", f"Search did not use the embedding index: {detail}")
    if r["hits"] < r["total"]:
        return _check("index_roundtrip", "fail", detail, missed=r["misses"])
    return _check("index_roundtrip", "pass", detail)


def retrieval_recall_check(fabric_id: str, probes: List[Dict[str, str]]) -> Dict[str, Any]:
    """Search with one sentence from known chunks and measure how often the chunk comes back.

    A quality measurement, not a gate: repeated or boilerplate text lowers it.
    """
    if not probes:
        return _check("retrieval_recall", "warn", "No passage was long enough to measure retrieval recall")
    r = _run_probes(fabric_id, probes)
    recall = r["hits"] / r["total"]
    detail = f"recall@{PROBE_TOP_K} = {recall:.0%} ({r['hits']} of {r['total']} single-sentence probes)"
    status = "pass" if recall >= 0.6 else "warn"
    return _check("retrieval_recall", status, detail, recall=round(recall, 3), missed=r["misses"])


def validate_tabular(
    fabric_id: str,
    tables: Dict[str, List[Dict[str, Any]]],
    profile: Dict[str, Any],
    store: TableStore,
    documents: List[Dict[str, Any]],
    *,
    check_rows: bool = True,
) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    stored = store.row_counts(fabric_id)

    if check_rows:
        mismatched = []
        for table in profile["tables"]:
            if not table["columns"]:
                continue
            expected = len(tables.get(table["name"]) or [])
            actual = stored.get(table["sql_name"], 0)
            if expected != actual:
                mismatched.append(f"{table['name']}: {actual:,} stored, {expected:,} read")
        total = sum(len(v) for v in tables.values())
        checks.append(
            _check("row_counts", "fail", "Rows lost while loading: " + "; ".join(mismatched))
            if mismatched
            else _check("row_counts", "pass", f"All {total:,} rows read are in the table store")
        )

        # Numeric integrity: the stored sum of each numeric column equals the sum of the values read.
        drift = []
        compared = 0
        for table in profile["tables"]:
            rows = tables.get(table["name"]) or []
            for col in table["columns"]:
                if col["type"] not in ("integer", "float") or not rows:
                    continue
                values = [
                    normalize_value(r.get(col["name"]), col["type"], col)
                    for r in rows if not is_null(r.get(col["name"]))
                ]
                expected_sum = math.fsum(float(v) for v in values)
                got = store.query(
                    fabric_id, f'SELECT SUM("{col["sql_name"]}") FROM "{table["sql_name"]}"', max_rows=1
                )["rows"][0][0]
                compared += 1
                if not math.isclose(float(got or 0.0), expected_sum, rel_tol=1e-9, abs_tol=1e-6):
                    drift.append(f"{table['name']}.{col['name']}: stored {got}, read {expected_sum}")
        if compared:
            checks.append(
                _check("numeric_integrity", "fail", "Numeric columns changed while loading: " + "; ".join(drift[:5]))
                if drift
                else _check("numeric_integrity", "pass", f"Sums of {compared} numeric column(s) match the source values")
            )

    for table in profile["tables"]:
        if table.get("is_sample"):
            checks.append(_check(
                "source_coverage", "warn",
                f"{table['name']}: {table['row_count']:,} of {table['source_row_count']:,} source rows imported; "
                f"answers describe the imported rows only",
            ))
    orphans = [fk for fk in profile.get("foreign_keys", []) if fk["orphan_values"]]
    for fk in orphans:
        checks.append(_check(
            "referential_integrity", "warn",
            f"{fk['from_table']}.{fk['from_column']} -> {fk['to_table']}.{fk['to_column']}: "
            f"{fk['orphan_values']} of {fk['distinct_values']} value(s) have no parent row",
        ))
    if profile.get("foreign_keys") and not orphans:
        checks.append(_check(
            "referential_integrity", "pass",
            f"All {len(profile['foreign_keys'])} discovered relationship(s) resolve to a parent row",
        ))
    no_key = profile["summary"].get("tables_without_key") or []
    if no_key:
        checks.append(_check("keys", "warn", "No unique key found for: " + ", ".join(no_key)))

    checks.append(index_count_check(fabric_id, len(documents)))

    picks: List[Dict[str, Any]] = [d for d in documents if d["metadata"].get("chunk_type") == "schema"][:2]
    entity_docs = [d for d in documents if d["metadata"].get("chunk_type") == "entity"]
    if entity_docs:
        picks += [entity_docs[i] for i in sorted({0, len(entity_docs) // 2, len(entity_docs) - 1})]
    probes = [{"id": d["id"], "query": d["content"], "content": d["content"]} for d in picks]
    checks.append(index_roundtrip_check(fabric_id, probes))
    return checks


def validate_documents(
    fabric_id: str,
    parsed_files: List[Dict[str, Any]],
    chunks: List[Dict[str, Any]],
    chunk_ids: List[str],
) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    per_file: Dict[str, int] = {}
    for chunk in chunks:
        per_file[chunk["file_name"]] = per_file.get(chunk["file_name"], 0) + 1
    empty = [p["file_name"] for p in parsed_files if not per_file.get(p["file_name"])]
    checks.append(
        _check("file_coverage", "fail", "No content was indexed for: " + ", ".join(empty))
        if empty
        else _check("file_coverage", "pass", f"All {len(parsed_files)} file(s) produced chunks")
    )

    for parsed in parsed_files:
        stats = parsed["stats"]
        if stats.get("pages_unreadable"):
            share = stats["pages_unreadable"] / max(1, stats["pages"])
            checks.append(_check(
                "page_coverage", "warn",
                f"{parsed['file_name']}: {stats['pages_unreadable']} of {stats['pages']} page(s) "
                f"({share:.0%}) have no readable text and are not in the fabric",
            ))
        if stats.get("pages_ocr"):
            checks.append(_check(
                "ocr", "warn",
                f"{parsed['file_name']}: {stats['pages_ocr']} page(s) were read by OCR; "
                f"OCR text can contain recognition errors",
            ))

    checks.append(index_count_check(fabric_id, len(chunks)))

    indexed = [(i, c) for i, c in enumerate(chunks) if i < len(chunk_ids)]
    step = max(1, len(indexed) // 5)
    checks.append(index_roundtrip_check(fabric_id, [
        {"id": chunk_ids[i], "query": c["content"], "content": c["content"]} for i, c in indexed[::step][:5]
    ]))

    recall_probes: List[Dict[str, str]] = []
    candidates = [(i, c) for i, c in indexed if c["block_type"] == "text" and len(c["body"]) >= 120]
    if candidates:
        step = max(1, len(candidates) // 10)
        for i, chunk in candidates[::step][:10]:
            sentences = [s for s in split_sentences(chunk["body"]) if len(s) >= 40]
            query = sentences[len(sentences) // 2] if sentences else chunk["body"][:200]
            recall_probes.append({
                "id": chunk_ids[i], "query": re.sub(r"\s+", " ", query)[:300], "content": chunk["content"],
            })
    checks.append(retrieval_recall_check(fabric_id, recall_probes))
    return checks
