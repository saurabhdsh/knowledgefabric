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


def test_group_by_outcome_counts():
    rows = _cyp_like_rows(90)
    result = analyze_tabular_query(
        rows,
        "Count compounds group by PUBCHEM_ACTIVITY_OUTCOME",
        fabric_name="CYP",
    )
    assert result is not None
    assert result["intent"] == "group_by_counts"
    assert result["group_by"] == "PUBCHEM_ACTIVITY_OUTCOME"
    assert result["metrics"]["counts"]["Active"] == 30
    assert "| PUBCHEM_ACTIVITY_OUTCOME |" in result["answer"]


def test_group_by_average_score():
    rows = _cyp_like_rows(90)
    result = analyze_tabular_query(
        rows,
        "What is the average PUBCHEM_ACTIVITY_SCORE by PUBCHEM_ACTIVITY_OUTCOME?",
        fabric_name="CYP",
    )
    assert result is not None
    assert result["intent"] == "group_average"
    assert result["group_by"] == "PUBCHEM_ACTIVITY_OUTCOME"
    assert "| PUBCHEM_ACTIVITY_OUTCOME | Count | Average | Min | Max |" in result["answer"]


def test_filter_active_with_score_gt():
    rows = _cyp_like_rows(150)
    result = analyze_tabular_query(
        rows,
        "How many Active compounds with PUBCHEM_ACTIVITY_SCORE > 40?",
        fabric_name="CYP",
    )
    assert result is not None
    assert result["intent"] in {"filtered_count", "filtered_value_counts", "filtered_empty"}
    expected = sum(
        1
        for r in rows
        if r["PUBCHEM_ACTIVITY_OUTCOME"] == "Active" and float(r["PUBCHEM_ACTIVITY_SCORE"]) > 40
    )
    assert result["row_total"] == expected
    assert "Filter:" in result["answer"] or "| Filter |" in result["answer"]


def test_filter_where_outcome_equals():
    rows = _cyp_like_rows(60)
    result = analyze_tabular_query(
        rows,
        "How many rows where PUBCHEM_ACTIVITY_OUTCOME = Inactive?",
        fabric_name="CYP",
    )
    assert result is not None
    assert result["row_total"] == 20
    assert result["intent"] in {"filtered_count", "filtered_value_counts"}


def test_intent_detects_group_by_and_filters():
    cols = ["status", "score", "PUBCHEM_ACTIVITY_OUTCOME"]
    assert is_analytical_query("group by status", columns=cols)
    assert is_analytical_query("count by status", columns=cols)
    assert is_analytical_query("average score by status", columns=cols)
    assert is_analytical_query("rows where status = OK", columns=cols)
    assert is_analytical_query("score > 40", columns=cols)
    assert is_analytical_query("Show me PUBCHEM_ACTIVITY_OUTCOME breakdown", columns=cols)


def test_analytics_snapshot_blocks_sample_reasoning():
    from app.services.analytics.tabular_analytics import build_fabric_analytics_snapshot

    rows = _cyp_like_rows(100)
    snap = build_fabric_analytics_snapshot(rows, fabric_name="CYP")
    assert snap is not None
    assert "FULL-FABRIC ANALYTICS SNAPSHOT" in snap
    assert "Indexed row chunks: 100" in snap
    assert "sample chunks" in snap.lower() or "Do NOT compute" in snap


def _claims_like_rows(n: int = 2000):
    statuses = ["In Review", "Denied", "Paid", "Pending"]
    payers = ["Aetna", "UHC", "Cigna"]
    rows = []
    for i in range(n):
        rows.append(
            {
                "claim_id": f"CLM{i}",
                "member_id": f"MBR{i % 100}",
                "adjudication_status": statuses[i % len(statuses)],
                "payer_name": payers[i % len(payers)],
                "claim_amount": 100 + (i % 50),
            }
        )
    return rows


def test_soft_group_by_status_resolves_adjudication_status():
    """NL 'group by status' must map to adjudication_status — not total_rows."""
    rows = _claims_like_rows(2000)
    result = analyze_tabular_query(
        rows,
        "Count claims group by status",
        fabric_name="ClaimsData",
    )
    assert result is not None
    assert result["intent"] == "group_by_counts"
    assert result["group_by"] == "adjudication_status"
    assert sum(result["metrics"]["counts"].values()) == 2000
    assert result["metrics"]["counts"]["In Review"] == 500
    assert "| adjudication_status |" in result["answer"]


def test_exact_group_by_column_still_works():
    rows = _claims_like_rows(100)
    result = analyze_tabular_query(
        rows,
        "Count group by adjudication_status",
        fabric_name="ClaimsData",
    )
    assert result is not None
    assert result["intent"] == "group_by_counts"
    assert result["group_by"] == "adjudication_status"


def test_average_amount_by_payer_soft_names():
    rows = _claims_like_rows(120)
    result = analyze_tabular_query(
        rows,
        "Average amount by payer",
        fabric_name="ClaimsData",
    )
    assert result is not None
    assert result["intent"] == "group_average"
    assert result["group_by"] == "payer_name"
    assert result["field"] == "claim_amount"


def test_how_many_claims_still_total_rows():
    rows = _claims_like_rows(2000)
    result = analyze_tabular_query(rows, "How many claims", fabric_name="ClaimsData")
    assert result is not None
    assert result["intent"] == "total_rows"
    assert result["row_total"] == 2000


def test_ambiguous_group_by_id_clarifies():
    rows = _claims_like_rows(40)
    result = analyze_tabular_query(
        rows,
        "Count claims group by id",
        fabric_name="ClaimsData",
    )
    assert result is not None
    assert result["intent"] == "group_by_unresolved"
    assert "clarification" in result["answer"].lower() or "Candidate columns" in result["answer"]
    assert "claim_id" in result["answer"] or "claim_id" in (result.get("metrics") or {}).get("candidates", [])


def test_soft_group_by_outcome_on_cyp_fabric():
    rows = _cyp_like_rows(90)
    result = analyze_tabular_query(
        rows,
        "Count compounds group by outcome",
        fabric_name="CYP",
    )
    assert result is not None
    assert result["intent"] == "group_by_counts"
    assert result["group_by"] == "PUBCHEM_ACTIVITY_OUTCOME"
