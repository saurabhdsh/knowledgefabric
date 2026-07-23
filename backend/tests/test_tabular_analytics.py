"""Validation: Test with LLM analytical queries run over full tabular fabrics."""
from __future__ import annotations

from app.services.analytics.tabular_analytics import (
    analyze_tabular_query,
    is_analytical_query,
    load_rows_from_source_documents,
    parse_row_text,
)
from app.services.document_service import document_service


def _cyp_like_rows(n: int = 200):
    """Synthetic NCATS CYP2C9-style rows (larger than sample_rows preview)."""
    outcomes = ["Active", "Inactive", "Inconclusive"]
    rows = []
    for i in range(n):
        outcome = outcomes[i % 3]
        # Skew: Active gets higher scores
        score = 40 - (i % 3) * 10 + (i % 7)
        rows.append(
            {
                "PUBCHEM_SID": str(100000 + i),
                "PUBCHEM_CID": str(500000 + (i % 50)),  # 50 unique CIDs
                "PUBCHEM_ACTIVITY_OUTCOME": outcome,
                "PUBCHEM_ACTIVITY_SCORE": score,
            }
        )
    return rows


def test_parse_row_text_pipe_format():
    row = parse_row_text(
        "PUBCHEM_SID: 104223880 | PUBCHEM_ACTIVITY_OUTCOME: Active | PUBCHEM_ACTIVITY_SCORE: 41"
    )
    assert row["PUBCHEM_ACTIVITY_OUTCOME"] == "Active"
    assert row["PUBCHEM_ACTIVITY_SCORE"] == "41"


def test_is_analytical_query_detects_true_analytics():
    assert is_analytical_query("How many compounds are Active, Inactive, and Inconclusive?")
    assert is_analytical_query("What is the average PUBCHEM_ACTIVITY_SCORE?")
    assert is_analytical_query("How many unique PUBCHEM_CID values are there?")
    assert is_analytical_query("Distribution of PUBCHEM_ACTIVITY_OUTCOME")
    assert is_analytical_query("What percentage are Active?")
    assert not is_analytical_query("Explain why SID 104223880 was marked Active")


def test_outcome_distribution_uses_all_rows_not_sample():
    rows = _cyp_like_rows(300)  # >> typical sample_rows of ~5–10
    result = analyze_tabular_query(
        rows,
        "How many compounds are Active, Inactive, and Inconclusive?",
        fabric_name="NCATS_CYP2C9_BioAssay",
    )
    assert result is not None
    assert result["intent"] == "value_counts"
    counts = result["metrics"]["counts"]
    assert counts["Active"] == 100
    assert counts["Inactive"] == 100
    assert counts["Inconclusive"] == 100
    assert result["row_total"] == 300
    answer = result["answer"]
    assert "| Category | Count | Percentage |" in answer
    assert "| Active | 100 |" in answer
    assert "## Summary" in answer
    assert "sample_rows" in answer  # mentioned as excluded in Notes


def test_total_row_count():
    rows = _cyp_like_rows(5247)
    result = analyze_tabular_query(rows, "How many compounds are in this fabric?", fabric_name="CYP")
    assert result is not None
    assert result["intent"] == "total_rows"
    assert result["row_total"] == 5247
    assert "| Total rows / compounds | 5247 |" in result["answer"]
    assert "## Summary" in result["answer"]


def test_average_activity_score():
    rows = _cyp_like_rows(30)
    result = analyze_tabular_query(
        rows,
        "What is the average PUBCHEM_ACTIVITY_SCORE?",
        fabric_name="CYP",
    )
    assert result is not None
    assert result["intent"] == "numeric_average"
    expected = sum(float(r["PUBCHEM_ACTIVITY_SCORE"]) for r in rows) / len(rows)
    assert abs(result["metrics"]["average"] - expected) < 1e-6
    assert "| Statistic | Value |" in result["answer"]
    assert "| Average |" in result["answer"]


def test_unique_cid_count():
    rows = _cyp_like_rows(200)
    result = analyze_tabular_query(
        rows,
        "How many unique PUBCHEM_CID values are there?",
        fabric_name="CYP",
    )
    assert result is not None
    assert result["intent"] == "unique_count"
    assert result["metrics"]["distinct"] == 50
    assert "| Distinct `PUBCHEM_CID` | 50 |" in result["answer"]


def test_percentage_breakdown():
    rows = _cyp_like_rows(99)
    result = analyze_tabular_query(
        rows,
        "What percentage of compounds are Active, Inactive, and Inconclusive?",
        fabric_name="CYP",
    )
    assert result is not None
    assert "| Percentage |" in result["answer"]
    assert "%" in result["answer"]
    assert "| Active |" in result["answer"]


def test_min_max_score():
    rows = _cyp_like_rows(45)
    result = analyze_tabular_query(
        rows,
        "What is the maximum PUBCHEM_ACTIVITY_SCORE?",
        fabric_name="CYP",
    )
    assert result is not None
    assert result["intent"] == "numeric_max"
    assert result["metrics"]["max"] == max(float(r["PUBCHEM_ACTIVITY_SCORE"]) for r in rows)
    assert "| Max |" in result["answer"]
    assert "**Highlighted:**" in result["answer"]


def test_document_service_row_chunks_feed_analytics():
    """End-to-end shape: CSV ingest → row chunks → analytics (no sample truncation)."""
    raw = _cyp_like_rows(120)
    docs = document_service.process_database_data(raw, "NCATS_CYP2C9_BioAssay")
    row_docs = [d for d in docs if (d.get("metadata") or {}).get("chunk_type") == "row"]
    assert len(row_docs) == 120

    documents = [d["content"] for d in row_docs]
    metadatas = [d["metadata"] for d in row_docs]
    rows = load_rows_from_source_documents(documents, metadatas)
    assert len(rows) == 120

    result = analyze_tabular_query(
        rows,
        "How many compounds are Active, Inactive, and Inconclusive?",
        fabric_name="NCATS_CYP2C9_BioAssay",
    )
    assert result["metrics"]["counts"]["Active"] == 40
    assert result["metrics"]["counts"]["Inactive"] == 40
    assert result["metrics"]["counts"]["Inconclusive"] == 40


def test_sample_preview_must_not_equal_full_counts():
    """Guards the exact failure mode from Test LLM screenshots."""
    full = _cyp_like_rows(5247)
    sample = full[:5]
    full_result = analyze_tabular_query(
        full,
        "How many compounds are Active, Inactive, and Inconclusive?",
        fabric_name="NCATS",
    )
    sample_result = analyze_tabular_query(
        sample,
        "How many compounds are Active, Inactive, and Inconclusive?",
        fabric_name="NCATS",
    )
    assert full_result["row_total"] == 5247
    assert sample_result["row_total"] == 5
    assert full_result["metrics"]["counts"] != sample_result["metrics"]["counts"]
