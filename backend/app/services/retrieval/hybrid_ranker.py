"""Phase 4 hybrid retrieval: keyword + vector fusion, rerank, token budget, confidence."""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]{2,}")


def content_tokens(text: str) -> List[str]:
    stop = {
        "the", "and", "for", "with", "that", "this", "from", "what", "how",
        "who", "are", "was", "were", "has", "have", "does", "did", "about",
    }
    return [t.lower() for t in _TOKEN.findall(text or "") if t.lower() not in stop]


def fuse_and_rerank(
    query: str,
    vector_chunks: Sequence[Dict[str, Any]],
    keyword_chunks: Sequence[Dict[str, Any]],
    *,
    top_k: int = 8,
) -> List[Dict[str, Any]]:
    """Fuse exact-token hits with vector hits, then rerank by overlap + similarity."""
    q_tokens = content_tokens(query)
    q_set = set(q_tokens)
    merged: Dict[str, Dict[str, Any]] = {}

    def _id(chunk: Dict[str, Any], fallback: str) -> str:
        return str(chunk.get("id") or fallback)

    for i, chunk in enumerate(keyword_chunks):
        cid = _id(chunk, f"kw-{i}")
        row = dict(chunk)
        row["keyword_hit"] = True
        row["vector_score"] = float(row.get("similarity_score") or 0.0)
        merged[cid] = row

    for i, chunk in enumerate(vector_chunks):
        cid = _id(chunk, f"vec-{i}")
        if cid in merged:
            merged[cid]["vector_score"] = max(
                float(merged[cid].get("vector_score") or 0.0),
                float(chunk.get("similarity_score") or 0.0),
            )
            merged[cid]["ranker"] = chunk.get("ranker") or merged[cid].get("ranker")
            if not merged[cid].get("content"):
                merged[cid]["content"] = chunk.get("content")
        else:
            row = dict(chunk)
            row["keyword_hit"] = False
            row["vector_score"] = float(chunk.get("similarity_score") or 0.0)
            merged[cid] = row

    ranked: List[Dict[str, Any]] = []
    for chunk in merged.values():
        body = str(chunk.get("content") or "")
        body_tokens = set(content_tokens(body))
        overlap = (len(q_set & body_tokens) / len(q_set)) if q_set else 0.0
        vector_score = float(chunk.get("vector_score") or 0.0)
        keyword_boost = 0.25 if chunk.get("keyword_hit") else 0.0
        # Lightweight rerank: lexical overlap dominates identifiers; vector covers paraphrase.
        score = (0.45 * overlap) + (0.40 * min(1.0, vector_score)) + keyword_boost
        chunk["lexical_overlap"] = round(overlap, 4)
        chunk["rerank_score"] = round(min(1.0, score), 4)
        ranked.append(chunk)

    ranked.sort(key=lambda c: float(c.get("rerank_score") or 0.0), reverse=True)
    return ranked[: max(1, int(top_k))]


def pack_with_budget(blocks: Sequence[str], budget_chars: int) -> Tuple[List[str], bool]:
    """Keep leading blocks until the character budget is spent."""
    used: List[str] = []
    size = 0
    truncated = False
    limit = max(500, int(budget_chars))
    for block in blocks:
        extra = len(block) + 2
        if used and size + extra > limit:
            truncated = True
            break
        used.append(block)
        size += extra
    if len(used) < len(blocks):
        truncated = True
    return used, truncated


def measure_confidence(
    query: str,
    chunks: Sequence[Dict[str, Any]],
    evidence_text: str,
    *,
    graph_fact_count: int = 0,
    sql_backed: bool = False,
) -> Dict[str, Any]:
    """Confidence from retrieval measurements, not a constant.

    Components:
    - rerank: best fused score
    - recall_proxy: share of query tokens present in evidence
    - graph: whether expansion returned facts
    - sql: exact tabular computation
    """
    q_tokens = content_tokens(query)
    ev_tokens = set(content_tokens(evidence_text))
    recall = (len(set(q_tokens) & ev_tokens) / len(set(q_tokens))) if q_tokens else 0.0
    best = max((float(c.get("rerank_score") or c.get("similarity_score") or 0.0) for c in chunks), default=0.0)
    keyword = any(c.get("keyword_hit") or c.get("ranker") == "exact-token" for c in chunks)
    graph = 1.0 if graph_fact_count else 0.0
    sql = 1.0 if sql_backed else 0.0
    score = (0.35 * best) + (0.35 * recall) + (0.15 * (1.0 if keyword else 0.0)) + (0.10 * graph) + (0.05 * sql)
    if sql_backed:
        score = max(score, 0.82)
    score = round(max(0.0, min(1.0, score)), 3)
    return {
        "confidence": score,
        "rerank": round(best, 3),
        "recall_proxy": round(recall, 3),
        "keyword_hit": keyword,
        "graph_facts": graph_fact_count,
        "sql_backed": sql_backed,
    }


def score_golden_item(
    item: Dict[str, Any],
    *,
    retrieved_text: str,
    answer: str,
) -> Dict[str, Any]:
    """Score one golden question: retrieval recall and answer groundedness."""
    must = [str(t).lower() for t in (item.get("must_retrieve") or [])]
    hay = (retrieved_text or "").lower()
    hits = [t for t in must if t in hay]
    recall = (len(hits) / len(must)) if must else 1.0
    claims = [str(c).lower() for c in (item.get("answer_must_mention") or [])]
    ans = (answer or "").lower()
    # Groundedness: required answer spans appear in BOTH the answer and the evidence.
    grounded = [c for c in claims if c in ans and c in hay]
    groundedness = (len(grounded) / len(claims)) if claims else (1.0 if ans.strip() else 0.0)
    return {
        "id": item.get("id"),
        "recall": round(recall, 3),
        "groundedness": round(groundedness, 3),
        "retrieved_hits": hits,
        "missing": [t for t in must if t not in hits],
        "passed": recall >= float(item.get("min_recall") or 0.5) and groundedness >= float(item.get("min_groundedness") or 0.5),
    }


def summarize_golden(results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = list(results)
    n = len(rows) or 1
    return {
        "questions": len(rows),
        "passed": sum(1 for r in rows if r.get("passed")),
        "mean_recall": round(sum(float(r.get("recall") or 0) for r in rows) / n, 3),
        "mean_groundedness": round(sum(float(r.get("groundedness") or 0) for r in rows) / n, 3),
        "results": rows,
    }
