"""Answering questions on Release 2.0 fabrics (Phase 1 + Phase 3 hybrid routing).

Routing:

1. Tabular data (fabric has a table store)
   a. identifiers / names in the question → exact entity lookup + FK expand;
   b. **structured** questions (counts, sums, rankings) → SQL over all rows;
   c. **mixed** questions (structured + narrative/policy intent) → SQL **and**
      document retrieval, packed together (``route=hybrid``);
   d. without an LLM, the rule-based analytics engine may answer structured Qs.
2. **Narrative** / everything else: semantic + exact-token retrieval, with
   linked document→row entity context injected when Phase 3 links exist.

The response says which route produced the answer and what it is based on.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.services.fabric_pipeline.chunker import citation
from app.services.fabric_pipeline.entity_resolution import linked_row_context_for_chunks
from app.services.fabric_pipeline.runner import load_profile
from app.services.fabric_pipeline.table_store import table_store
from app.services.fabric_pipeline.tabular_index import dataset_card
from app.services.fabric_pipeline.tabular_query import (
    LLMCall,
    _candidate_tokens,
    answer_with_sql,
    entity_context_text,
    find_entities,
    looks_structured,
)
from app.services.vector_service import vector_service

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 12
MAX_EXACT_PER_TOKEN = 4

_NARRATIVE_RE = re.compile(
    r"\b(policy|policies|guideline|guidelines|according to|explain|describe|what does|"
    r"narrative|document|pdf|section|eligible|eligibility|exclusion|exclusions|"
    r"outreach|follow[- ]?up|care plan|procedure|how (?:should|do|does|can)|why|"
    r"recommend|recommendation|criteria|definition|means|summarise|summarize)\b",
    re.I,
)


def is_v2_fabric(fabric: Optional[Dict[str, Any]]) -> bool:
    return bool(fabric) and int(fabric.get("pipeline_version") or 1) >= 2 and fabric.get("status") != "failed"


def tabular_profile(fabric: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Profile of a fabric's table store, or ``None`` when it has no queryable tables."""
    fabric_id = str(fabric.get("id") or "")
    if not is_v2_fabric(fabric) or not table_store.exists(fabric_id):
        return None
    return load_profile(fabric_id)


def looks_narrative(query: str) -> bool:
    """Whether a question likely needs document / policy passages."""
    return bool(_NARRATIVE_RE.search(query or ""))


def classify_query_intent(query: str, profile: Optional[Dict[str, Any]]) -> str:
    """Return ``structured`` | ``narrative`` | ``mixed``."""
    structured = bool(profile) and looks_structured(query, profile)
    narrative = looks_narrative(query)
    if structured and narrative:
        return "mixed"
    if structured:
        return "structured"
    return "narrative"


def _chunk_reference(chunk: Dict[str, Any]) -> str:
    meta = chunk.get("metadata") or {}
    chunk_type = str(meta.get("chunk_type") or "")
    origin = meta.get("composite_origin_source_name")
    if chunk_type in ("entity", "text"):
        ref = f"{meta.get('source_collection', 'table')} {meta.get('row_key', '')}".strip()
    elif chunk_type == "schema":
        ref = f"schema of {meta.get('source_collection', 'table')}"
    elif chunk_type == "dataset":
        ref = "dataset overview"
    else:
        ref = citation(meta, str(meta.get("file_name") or ""))
    if origin:
        ref = f"{origin}: {ref}" if ref else str(origin)
    return ref or "fabric"


def _pack(blocks: List[str], budget: int) -> List[str]:
    used: List[str] = []
    size = 0
    for block in blocks:
        if used and size + len(block) > budget:
            break
        used.append(block)
        size += len(block) + 2
    return used


def _rule_engine_answer(fabric: Dict[str, Any], profile: Dict[str, Any], query: str) -> Optional[Dict[str, Any]]:
    """Rule-based analytics over the table store rows (used when no LLM is available)."""
    from app.services.analytics.tabular_analytics import analyze_tabular_query, is_analytical_query

    fabric_id = str(fabric["id"])
    tables = [t for t in profile["tables"] if t["row_count"]]
    if not tables:
        return None
    lowered = query.lower()
    target = next((t for t in tables if t["name"].lower() in lowered or t["name"].lower().rstrip("s") in lowered), None)
    target = target or max(tables, key=lambda t: t["row_count"])
    columns = [c["name"] for c in target["columns"]]
    if not is_analytical_query(query, columns=columns):
        return None
    rows = table_store.original_rows(fabric_id, profile, table=target["name"])
    for row in rows:
        row.pop("__source_collection", None)
    result = analyze_tabular_query(rows, query, fabric_name=str(fabric.get("name") or fabric_id))
    if not result or not result.get("answer"):
        return None
    return {
        "answer": result["answer"],
        "intent": result.get("intent"),
        "metrics": result.get("metrics"),
        "table": target["name"],
        "row_total": len(rows),
    }


def _run_sql(
    fabric: Dict[str, Any],
    profile: Dict[str, Any],
    query: str,
    llm: LLMCall,
    entity_text: str,
) -> Dict[str, Any]:
    fabric_id = str(fabric["id"])
    fabric_name = str(fabric.get("name") or fabric_id)
    try:
        sql_result = answer_with_sql(
            fabric_id, fabric_name, profile, query, llm, table_store, extra_context=entity_text
        )
    except Exception as exc:
        logger.warning("SQL route failed for %s: %s", fabric_id, exc)
        return {"answer": None, "error": str(exc)}
    return sql_result or {"answer": None}


def _retrieve_chunks(
    fabric_id: str,
    query: str,
    top_k: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str, float]:
    """Keyword + vector candidates, fused and reranked to ``top_k``."""
    from app.services.retrieval.hybrid_ranker import fuse_and_rerank

    vector_chunks = vector_service.search_similar_chunks(query, fabric_id, top_k=max(top_k * 3, top_k))
    ranker = (vector_chunks[0].get("ranker") if vector_chunks else "") or "hybrid"
    exact_chunks: List[Dict[str, Any]] = []
    seen_ids = set()
    for token in _candidate_tokens(query)[0][:4]:
        for chunk in vector_service.find_chunks_containing(fabric_id, token, limit=MAX_EXACT_PER_TOKEN):
            if chunk.get("id") not in seen_ids:
                seen_ids.add(chunk.get("id"))
                chunk = dict(chunk)
                chunk["ranker"] = "exact-token"
                exact_chunks.append(chunk)
    chunks = fuse_and_rerank(query, vector_chunks, exact_chunks, top_k=top_k)
    top_score = float(chunks[0].get("rerank_score") or 0.0) if chunks else 0.0
    return chunks, exact_chunks, f"hybrid+{ranker}", top_score



def _fitted_confidence_weights(fabric_id: str):
    """Weights fitted from thumbs up/down for this fabric, or None."""
    try:
        from app.db.models import FabricFeedbackRecord, RetrievalEpisodeRecord
        from app.db.session import get_session_factory
        from app.services.retrieval.hybrid_ranker import fit_confidence_weights

        session = get_session_factory()()
        try:
            feedback = (
                session.query(FabricFeedbackRecord)
                .filter(FabricFeedbackRecord.fabric_id == fabric_id)
                .order_by(FabricFeedbackRecord.created_at.desc())
                .limit(500)
                .all()
            )
            if len(feedback) < 20:
                return None
            episodes = []
            for row in feedback:
                measurement = {}
                if row.episode_id:
                    ep = session.get(RetrievalEpisodeRecord, row.episode_id)
                    if ep and isinstance(getattr(ep, "payload", None), dict):
                        measurement = (ep.payload or {}).get("measurement") or {}
                    elif ep:
                        measurement = {
                            "rerank": getattr(ep, "confidence", None),
                        }
                episodes.append({
                    "rating": row.rating,
                    "measurement": measurement or {"rerank": 0.5, "recall_proxy": 0.5},
                })
            return fit_confidence_weights(episodes)
        finally:
            session.close()
    except Exception:
        logger.debug("Could not fit confidence weights for %s", fabric_id, exc_info=True)
        return None



def _mask_rows(fabric: Dict[str, Any], rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Hide classified PII columns in rows returned to the caller."""
    sensitive = list((fabric.get("pii") or {}).get("sensitive_columns") or fabric.get("sensitive_columns") or [])
    if not sensitive:
        return rows
    from app.services.enterprise.ops import redact_row
    return [redact_row(row, sensitive) for row in rows]


def answer_query(
    fabric: Dict[str, Any],
    query: str,
    *,
    llm: Optional[LLMCall],
    system_prompt: str,
    top_k: Optional[int] = None,
    memory_context: str = "",
    ontology_context: str = "",
    ontology_version_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Answer one question. ``llm`` is ``None`` when no provider is available."""
    from app.services.context.envelope import begin_envelope, finish_envelope, render_memory, render_ontology

    env = begin_envelope(memory_context, ontology_context, ontology_version_id)
    memory_context = render_memory(env)
    ontology_context = render_ontology(env)
    sql_answer_text = ""
    fabric_id = str(fabric["id"])
    fabric_name = str(fabric.get("name") or fabric_id)
    profile = tabular_profile(fabric)
    intent = classify_query_intent(query, profile)
    out: Dict[str, Any] = {
        "route": "retrieval",
        "intent": intent,
        "answer": "",
        "confidence": None,
        "confidence_basis": "",
        "relevant_chunks": 0,
        "citations": [],
        "sql": None,
        "analytics": None,
        "entities": [],
        "retrieval": {},
        "notes": [],
    }

    def _seal(evidence_chunks: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        table_text = ""
        if out.get("route") in {"sql", "rules"}:
            table_text = str(out.get("answer") or "")
        elif sql_answer_text:
            table_text = sql_answer_text
        out["context_envelope"] = finish_envelope(
            env,
            route=out.get("route"),
            confidence=out.get("confidence"),
            confidence_basis=out.get("confidence_basis"),
            measurement=(out.get("retrieval") or {}).get("measurement"),
            sql=out.get("sql"),
            table_text=table_text,
            entities=out.get("entities"),
            chunks=evidence_chunks or [],
        )
        return out

    entity_text = ""
    entity_bases: set = set()
    if profile:
        try:
            entities = find_entities(fabric_id, profile, query, table_store)
        except Exception as exc:
            logger.warning("Entity lookup failed for %s: %s", fabric_id, exc)
            entities = []
        if entities:
            entity_text = entity_context_text(entities)
            entity_bases = {str(e.get("basis") or "identifier") for e in entities}
            out["entities"] = [
                {
                    "table": e["table"], "column": e["matched_column"], "value": e["matched_value"],
                    "basis": e.get("basis") or "identifier", "confidence": e.get("confidence", 1.0),
                }
                for e in entities
            ]
            # Full rows for deterministic Context Layer adjudication (not always sent to clients).
            out["entity_rows"] = [
                {
                    "table": e.get("table"),
                    "matched_column": e.get("matched_column"),
                    "matched_value": e.get("matched_value"),
                    "row": e.get("row") or {},
                    "parents": e.get("parents") or [],
                    "children": e.get("children") or [],
                }
                for e in entities
            ]
            if "ambiguous_name" in entity_bases:
                out["notes"].append(
                    "A name in the question matches more than one row. Say that there are several "
                    "records with this name and ask which one is meant, or answer for each separately."
                )

    # ---- Structured-only: SQL / rules, early return ----
    if intent == "structured" and profile:
        if llm is not None:
            sql_result = _run_sql(fabric, profile, query, llm, entity_text)
            if sql_result and sql_result.get("answer"):
                out.update({
                    "route": "sql",
                    "answer": sql_result["answer"],
                    "sql": sql_result["sql"],
                    "analytics": {
                        "engine": "sql",
                        "sql": sql_result["sql"],
                        "explanation": sql_result.get("explanation"),
                        "columns": sql_result["columns"],
                        "rows": _mask_rows(fabric, sql_result["rows"][:200]),
                        "row_count": sql_result["row_count"],
                        "truncated": sql_result["truncated"],
                        "is_sample": sql_result["is_sample"],
                    },
                    "relevant_chunks": sql_result["row_count"],
                    "confidence_basis": (
                        "Computed by SQL over "
                        + ("the imported sample of the source" if sql_result["is_sample"] else "all rows in the fabric")
                        + "; the statement and result are included."
                    ),
                })
                return _seal()
            if sql_result and sql_result.get("error"):
                out["notes"].append(f"A SQL answer was attempted and failed: {sql_result['error']}")
        else:
            try:
                rules = _rule_engine_answer(fabric, profile, query)
            except Exception as exc:
                logger.warning("Rule engine failed for %s: %s", fabric_id, exc)
                rules = None
            if rules:
                out.update({
                    "route": "rules",
                    "answer": rules["answer"],
                    "analytics": {
                        "engine": "rules", "intent": rules.get("intent"), "metrics": rules.get("metrics"),
                        "table": rules["table"],
                    },
                    "relevant_chunks": rules["row_total"],
                    "confidence_basis": f"Computed by the rule engine over all {rules['row_total']:,} rows of '{rules['table']}'.",
                })
                return _seal()

    # ---- Mixed: SQL + retrieval ----
    sql_block = ""
    sql_payload: Optional[Dict[str, Any]] = None
    if intent == "mixed" and profile and llm is not None:
        sql_result = _run_sql(fabric, profile, query, llm, entity_text)
        if sql_result and sql_result.get("answer"):
            sql_payload = sql_result
            sql_answer_text = str(sql_result["answer"])
            sql_block = (
                "SQL RESULT (exact, from the table store):\n"
                f"SQL: {sql_result.get('sql')}\n"
                f"Answer: {sql_result['answer']}\n"
            )
            out["sql"] = sql_result["sql"]
            out["analytics"] = {
                "engine": "sql",
                "sql": sql_result["sql"],
                "explanation": sql_result.get("explanation"),
                "columns": sql_result["columns"],
                "rows": _mask_rows(fabric, sql_result["rows"][:200]),
                "row_count": sql_result["row_count"],
                "truncated": sql_result["truncated"],
                "is_sample": sql_result["is_sample"],
            }
        elif sql_result and sql_result.get("error"):
            out["notes"].append(f"A SQL answer was attempted and failed: {sql_result['error']}")

    k = int(top_k) if top_k and int(top_k) > 0 else DEFAULT_TOP_K
    chunks, exact_chunks, ranker, top_score = _retrieve_chunks(fabric_id, query, k)
    out["relevant_chunks"] = len(chunks)

    # Phase 3: inject row context for entities linked from retrieved document chunks
    link_text = ""
    if profile and chunks:
        try:
            link_text = linked_row_context_for_chunks(fabric_id, profile, chunks, table_store)
        except Exception as exc:
            logger.warning("Linked entity context failed for %s: %s", fabric_id, exc)

    blocks: List[str] = []
    if profile:
        blocks.append("DATASET OVERVIEW (exact, from the table store):\n" + dataset_card(profile, fabric_name))
    if sql_block:
        blocks.append(sql_block)
    if entity_text:
        if entity_bases <= {"identifier"}:
            blocks.append("EXACT RECORD LOOKUP (rows fetched by identifier, with related rows):\n" + entity_text)
        else:
            blocks.append(
                "RECORD LOOKUP (rows fetched by identifier or by name; each row states how it was "
                "matched, with related rows):\n" + entity_text
            )
    if link_text and link_text != entity_text:
        blocks.append(
            "ROWS LINKED FROM DOCUMENTS (Phase 3 entity resolution — mentions in policy/care text "
            "matched to table rows):\n" + link_text
        )
    if ontology_context:
        blocks.append("ONTOLOGY CONTEXT:\n" + ontology_context)
    fixed = len(blocks)
    for i, chunk in enumerate(chunks, start=1):
        ref = _chunk_reference(chunk)
        exact = chunk.get("ranker") == "exact-token"
        out["citations"].append({
            "n": i,
            "reference": ref,
            "match": "exact-token" if exact else "semantic",
            "score": None if exact else round(float(chunk.get("similarity_score") or 0.0), 4),
            "chunk_id": chunk.get("id"),
            "linked_entities": (chunk.get("metadata") or {}).get("linked_entity_count") or 0,
        })
        blocks.append(f"[{i}] ({ref})\n{chunk.get('content', '')}")
    budget = int(getattr(settings, "QUERY_TOKEN_BUDGET_CHARS", 12000) or 12000)
    hard_cap = int(settings.QUERY_MAX_CONTEXT_CHARS or 350_000)
    packed = _pack(blocks, min(budget, hard_cap))
    evidence_text = "\n".join(packed)
    from app.services.retrieval.hybrid_ranker import fit_confidence_weights, measure_confidence

    fitted = _fitted_confidence_weights(fabric_id)
    measurement = measure_confidence(
        query,
        chunks,
        evidence_text,
        graph_fact_count=evidence_text.lower().count("graph facts"),
        sql_backed=bool(sql_payload),
        weights=fitted,
    )
    out["retrieval"] = {
        "ranker": ranker,
        "top_k": k,
        "exact_token_chunks": len(exact_chunks),
        "retrieved_chunks": len(chunks),
        "packed_chunks": max(0, len(packed) - fixed),
        "context_truncated": len(packed) < len(blocks),
        "top_similarity": round(top_score, 4),
        "token_budget_chars": min(budget, hard_cap),
        "measurement": measurement,
        "intent": intent,
    }
    if chunks or entity_text or sql_payload:
        out["confidence"] = measurement["confidence"] if (chunks or sql_payload or entity_text) else None
        basis = []
        if sql_payload:
            basis.append("SQL over the table store")
        if entity_text:
            if "ambiguous_name" in entity_bases:
                basis.append("a name that matches more than one record")
            elif entity_bases <= {"identifier"}:
                basis.append("exact record lookup")
            else:
                basis.append("record lookup by name")
        if link_text:
            basis.append("document→row entity links")
        if exact_chunks:
            basis.append(f"{len(exact_chunks)} passage(s) containing the identifier in the question")
        if chunks and top_score:
            basis.append(
                f"top semantic similarity {top_score:.2f} ({ranker or 'no ranker'}), "
                f"which measures closeness of meaning, not correctness"
            )
        text = "; ".join(basis)
        out["confidence_basis"] = (text[:1].upper() + text[1:] + ".") if text else ""

    if intent == "mixed" and (sql_payload or chunks):
        out["route"] = "hybrid"
    elif entity_text and chunks:
        out["route"] = "entity+retrieval"
    elif link_text and chunks:
        out["route"] = "linked+retrieval"

    if llm is None:
        lines = ["No language model is configured, so this is the retrieved evidence rather than a written answer."]
        if sql_block:
            lines += ["", "**SQL result**", "```", sql_block, "```"]
        if entity_text:
            lines += ["", "**Exact record lookup**", "```", entity_text, "```"]
        if link_text:
            lines += ["", "**Document-linked rows**", "```", link_text, "```"]
        for c, chunk in zip(out["citations"][:5], chunks[:5]):
            how = "exact match" if c["match"] == "exact-token" else f"similarity {c['score']}"
            lines += ["", f"**[{c['n']}] {c['reference']}** ({how})", str(chunk.get("content", ""))[:1200]]
        if not chunks and not entity_text and not sql_payload:
            lines.append("Nothing in the fabric matched the question.")
        out["answer"] = "\n".join(lines)
        out["route"] = "evidence-only" if out["route"] != "hybrid" else "hybrid"
        return _seal(chunks)

    if not chunks and not entity_text and not sql_payload and not link_text:
        out["answer"] = "Nothing in this fabric matched the question, so there is no evidence to answer it from."
        out["route"] = "no-evidence"
        return _seal()

    memory_block = f"\n{memory_context}\n" if memory_context else ""
    hybrid_note = ""
    if intent == "mixed":
        hybrid_note = (
            "- This is a mixed question: use the SQL RESULT for counts/totals and the document "
            "passages for policy or narrative context. Cite both.\n"
        )
    context_contract = "DESIGNED CONTEXT LAYER" in (memory_context or "")
    decision_tail = (
        "\n- A DESIGNED CONTEXT LAYER is attached. After SUMMARY and EVIDENCE, you MUST end with:\n"
        "## DECISION\n"
        "- decision: pay|deny|hold|human_review\n"
        "- confidence_0_1: <number>\n"
        "- evidence_fields: <fields used>\n"
        "- reasoning_one_line: <one sentence>\n"
        "- Apply the Context Layer business rules literally; do not stop at IMPLICATIONS/UNKNOWNS.\n"
        "- Prefer a specific route (pay/deny/hold) over human_review when the claim row is present "
        "and a rule matches. Use human_review only when the claim row is missing or required "
        "fields (e.g. denial_reason on Denied) are absent.\n"
        if context_contract
        else ""
    )
    user_prompt = (
        f"Question: {query}\n{memory_block}\n"
        f"Evidence from the knowledge fabric '{fabric_name}':\n\n" + "\n\n".join(packed) + "\n\n"
        "Answer the question from this evidence only.\n"
        "- Cite the passages you use with their bracket numbers, e.g. [2]. Rows from the exact "
        "record lookup or document-linked rows can be cited as (record lookup).\n"
        "- Figures in DATASET OVERVIEW, SQL RESULT, RECORD LOOKUP and ROWS LINKED FROM "
        "DOCUMENTS are exact; prefer them over anything inferred from passages.\n"
        f"{hybrid_note}"
        "- If the evidence does not contain the answer, say so plainly instead of guessing.\n"
        "- If APPROVED FABRIC MEMORY is present, treat those corrections as authoritative.\n"
        "- Use Markdown; use a table for lists of records or numbers."
        f"{decision_tail}"
    )
    if out["notes"]:
        user_prompt += "\nNote: " + " ".join(out["notes"])
    # Context Layer runs colder so narration varies less before deterministic lock.
    temperature = 0.0 if context_contract else 0.2
    out["answer"] = llm(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        int(settings.QUERY_MAX_COMPLETION_TOKENS),
        temperature,
    )
    return _seal(chunks)


def vector_chunks_ok(top_score: float, chunks: List[Dict[str, Any]]) -> bool:
    return bool(chunks) and top_score > 0
