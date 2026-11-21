"""Coverage gaps are questions the envelope could not name or could not evidence."""
from app.services.context.studio import coverage_from_episodes


def test_coverage_flags_missing_ontology_and_missing_evidence():
    episodes = [
        {
            "query": "Should we outreach Lisa?",
            "route": "hybrid",
            "confidence": 0.4,
            "context_envelope": {"route": "hybrid", "lines": [{"kind": "table", "text": "Lisa Chen"}]},
        },
        {
            "query": "Should we outreach Lisa?",
            "route": "hybrid",
            "confidence": 0.5,
            "context_envelope": {"route": "hybrid", "lines": [{"kind": "passage", "text": "policy"}]},
        },
        {
            "query": "How many members?",
            "route": "sql",
            "confidence": 0.9,
            "context_envelope": {
                "route": "sql",
                "lines": [
                    {"kind": "ontology", "text": "Members"},
                    {"kind": "table", "text": "520"},
                ],
            },
        },
        {
            "query": "What does the policy require?",
            "route": "retrieval",
            "confidence": 0.3,
            "context_envelope": {"route": "retrieval", "lines": [{"kind": "ontology", "text": "Care plan"}]},
        },
    ]
    gaps = coverage_from_episodes(episodes)
    by_query = {gap["query"]: gap for gap in gaps}
    assert "How many members?" not in by_query
    assert by_query["Should we outreach Lisa?"]["gap"] == "no_ontology"
    assert by_query["Should we outreach Lisa?"]["count"] == 2
    assert by_query["What does the policy require?"]["gap"] == "no_evidence"
