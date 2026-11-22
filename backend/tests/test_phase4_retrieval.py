"""Phase 4 hybrid ranker, graph facts, and golden-set measurement."""
from __future__ import annotations

import json
from pathlib import Path

from app.services.retrieval.hybrid_ranker import (
    fuse_and_rerank,
    measure_confidence,
    pack_with_budget,
    score_golden_item,
    summarize_golden,
)
from app.services.retrieval.retrieval_orchestrator import RetrievalOrchestrator


def test_fuse_prefers_keyword_and_overlap():
    query = "MEM-LISA-COPD claims"
    vector = [
        {"id": "a", "content": "unrelated policy text about networks", "similarity_score": 0.91},
        {"id": "b", "content": "Member MEM-LISA-COPD has claims", "similarity_score": 0.42},
    ]
    keyword = [{"id": "b", "content": "Member MEM-LISA-COPD has claims", "ranker": "exact-token"}]
    ranked = fuse_and_rerank(query, vector, keyword, top_k=2)
    assert ranked[0]["id"] == "b"
    assert ranked[0]["keyword_hit"] is True
    assert ranked[0]["rerank_score"] >= ranked[1]["rerank_score"]


def test_token_budget_truncates():
    blocks = ["alpha " * 40, "beta " * 40, "gamma " * 40]
    packed, truncated = pack_with_budget(blocks, 120)
    assert truncated
    assert len(packed) < len(blocks)
    assert packed[0].startswith("alpha")


def test_confidence_rises_with_evidence_and_sql():
    weak = measure_confidence("member cost", [], "")
    strong = measure_confidence(
        "How many claims does MEM-LISA-COPD have?",
        [{"id": "1", "content": "MEM-LISA-COPD has 10 claims", "rerank_score": 0.8, "keyword_hit": True}],
        "MEM-LISA-COPD has 10 claims",
        sql_backed=True,
    )
    assert strong["confidence"] > weak["confidence"]
    assert strong["sql_backed"] is True
    assert 0.0 <= strong["confidence"] <= 1.0


def test_graph_facts_include_property_values():
    orch = RetrievalOrchestrator()
    facts = orch.graph_facts(
        {
            "nodes": [
                {
                    "id": "n1",
                    "label": "Lisa Chen",
                    "source_table": "members",
                    "properties": {"member_id": "MEM-LISA-COPD", "risk_tier": "High"},
                },
                {
                    "id": "n2",
                    "label": "CD-LISA-01",
                    "source_table": "cost_drivers",
                    "properties": {"driver_category": "Avoidable ER"},
                },
            ],
            "edges": [
                {
                    "source": "n1",
                    "target": "n2",
                    "relationship_type": "has_cost_driver",
                    "confidence": 0.93,
                }
            ],
        },
        [],
    )
    text = " ".join(facts)
    assert "MEM-LISA-COPD" in text
    assert "Avoidable ER" in text
    assert "has_cost_driver" in text
    assert "Relationship:" not in text


def test_golden_set_scores_recall_and_groundedness():
    path = Path(__file__).resolve().parent / "golden" / "cost_of_care.json"
    spec = json.loads(path.read_text())
    assert len(spec["questions"]) >= 25
    evidence = "Member MEM-LISA-COPD Lisa Chen has 10 claims. Cost driver Avoidable ER."
    answer = "Lisa Chen (MEM-LISA-COPD) has 10 claims driven by Avoidable ER."
    # The three original questions still require a perfect match on this evidence.
    core = [q for q in spec["questions"] if q["id"] in {"member-lisa", "avoidable-er", "claim-count"}]
    results = [score_golden_item(item, retrieved_text=evidence, answer=answer) for item in core]
    summary = summarize_golden(results)
    assert summary["questions"] == 3
    assert summary["passed"] == 3
    assert summary["mean_recall"] == 1.0
    assert summary["mean_groundedness"] == 1.0
