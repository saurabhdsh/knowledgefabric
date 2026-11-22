"""Key discovery must recover declared foreign keys and invent none.

This is the gate for the tabular relationship finder: on schemas with a known
ground truth, every declared link is found and nothing outside that set (or the
forbidden columns) is accepted.
"""
from __future__ import annotations

import pytest

from app.services.fabric_pipeline.tabular_profiler import profile_tables
from tests.fixtures.fk_benchmark import ALL_SCHEMAS, score_discovery


def _found_edges(profile):
    return {
        (fk["from_table"], fk["from_column"], fk["to_table"], fk["to_column"])
        for fk in profile.get("foreign_keys") or []
    }


@pytest.mark.parametrize("factory", ALL_SCHEMAS, ids=lambda f: f.__name__)
def test_declared_keys_are_found_and_no_wrong_keys_are_accepted(factory):
    schema = factory()
    profile = profile_tables(schema["tables"])
    found = _found_edges(profile)
    score = score_discovery(set(schema["declared"]), found)

    assert score["false_negatives"] == [], (
        f"{schema['name']}: missed declared keys {score['false_negatives']}"
    )
    assert score["false_positives"] == [], (
        f"{schema['name']}: invented keys {score['false_positives']}"
    )
    assert score["precision"] == 1.0 and score["recall"] == 1.0

    for table, column in schema.get("forbidden") or set():
        assert not any(f[0] == table and f[1] == column for f in found), (
            f"{schema['name']}: treated {table}.{column} as a foreign key"
        )
    for link in schema.get("forbidden_links") or set():
        assert link not in found, f"{schema['name']}: accepted forbidden link {link}"
        # A lookalike may sit in the review list; it must not be accepted.
        for cand in profile.get("foreign_key_candidates") or []:
            if cand.get("status") != "needs_review":
                continue
            edge = (cand["from_table"], cand["from_column"], cand["to_table"], cand["to_column"])
            if edge == link:
                break


def test_benchmark_summary_stays_perfect():
    """One aggregate number so a regression is obvious in the suite output."""
    totals = {"declared": 0, "found": 0, "wrong": 0, "missed": 0}
    for factory in ALL_SCHEMAS:
        schema = factory()
        score = score_discovery(set(schema["declared"]), _found_edges(profile_tables(schema["tables"])))
        totals["declared"] += len(score["declared"])
        totals["found"] += len(score["true_positives"])
        totals["wrong"] += len(score["false_positives"])
        totals["missed"] += len(score["false_negatives"])
    assert totals == {"declared": totals["declared"], "found": totals["declared"], "wrong": 0, "missed": 0}
    assert totals["declared"] >= 12
