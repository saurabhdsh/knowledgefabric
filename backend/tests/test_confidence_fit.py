"""Confidence blend can be fitted to thumbs up/down."""
from app.services.retrieval.hybrid_ranker import (
    DEFAULT_CONFIDENCE_WEIGHTS,
    fit_confidence_weights,
    measure_confidence,
)


def test_fit_needs_enough_ratings():
    assert fit_confidence_weights([{"rating": "up", "rerank": 0.9, "recall_proxy": 0.9}] * 5) is None


def test_fit_raises_sql_weight_when_sql_answers_are_thumbed_up():
    episodes = []
    for i in range(30):
        episodes.append({
            "rating": "up",
            "measurement": {"rerank": 0.2, "recall_proxy": 0.2, "keyword_hit": False, "graph_facts": 0, "sql_backed": True},
        })
    for i in range(10):
        episodes.append({
            "rating": "down",
            "measurement": {"rerank": 0.9, "recall_proxy": 0.9, "keyword_hit": True, "graph_facts": 0, "sql_backed": False},
        })
    weights = fit_confidence_weights(episodes, min_ratings=20)
    assert weights is not None
    assert weights["sql"] > DEFAULT_CONFIDENCE_WEIGHTS["sql"]
    strong = measure_confidence("how many?", [], "total 12", sql_backed=True, weights=weights)
    weak = measure_confidence("how many?", [{"rerank_score": 0.9, "keyword_hit": True}], "total 12", weights=weights)
    assert strong["confidence"] >= weak["confidence"]
