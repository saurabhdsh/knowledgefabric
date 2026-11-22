"""Foreign-key discovery: accept only what the values prove; list the rest for review."""
from __future__ import annotations

import random

import pytest

from app.services.fabric_pipeline.tabular_profiler import (
    apply_relationship_decisions,
    profile_tables,
    wilson_lower,
)


def _edge(fk):
    return (fk["from_table"], fk.get("from_column") or tuple(fk.get("from_columns") or []),
            fk["to_table"], fk.get("to_column") or tuple(fk.get("to_columns") or []))


def test_wilson_lower_penalises_tiny_samples():
    # Two matches out of two is weak; forty out of forty is strong.
    assert wilson_lower(2, 2) < 0.4
    assert wilson_lower(40, 40) > 0.9
    assert wilson_lower(0, 10) == 0.0


def test_clean_named_key_is_accepted():
    random.seed(1)
    customers = [{"customer_id": f"C{i:04d}", "customer_name": f"Cust {i}"} for i in range(1, 501)]
    orders = [{"order_id": f"O{i:05d}", "customer_id": f"C{random.randint(1, 500):04d}"} for i in range(1, 1501)]
    p = profile_tables({"customers": customers, "orders": orders})
    assert _edge(p["foreign_keys"][0]) == ("orders", "customer_id", "customers", "customer_id")
    assert p["foreign_keys"][0]["status"] == "accepted"
    assert p["foreign_keys"][0]["confidence"] > 0.9
    assert p["foreign_key_candidates"] == []


def test_sampled_parent_is_listed_for_review_not_accepted():
    random.seed(2)
    customers = [{"customer_id": f"C{i:04d}", "customer_name": f"Cust {i}"} for i in range(1, 1001)]
    orders = [{"order_id": f"O{i:05d}", "customer_id": f"C{random.randint(1, 1000):04d}"} for i in range(1, 3001)]
    p = profile_tables(
        {"customers": customers[:500], "orders": orders},
        {"customers": 1000, "orders": 3000},
    )
    assert p["foreign_keys"] == []
    review = p["foreign_key_candidates"]
    assert len(review) == 1 and review[0]["status"] == "needs_review"
    assert review[0]["parent_is_sample"] is True
    assert any("sample" in r for r in review[0]["review_reasons"])
    assert any("sample" in w and "needs review" in w for w in p["warnings"])


def test_orphans_in_the_review_band_are_listed_not_accepted():
    # 50 good parent keys + 20 orphans → overlap ≈ 0.71, in the review band.
    parents = [{"dept_id": f"D{i}", "dept_name": f"Dept {i}"} for i in range(1, 51)]
    children = [{"emp_id": f"E{i}", "dept_id": f"D{(i % 50) + 1}"} for i in range(1, 401)]
    for i in range(20):
        children.append({"emp_id": f"X{i}", "dept_id": f"MISSING-{i}"})
    p = profile_tables({"departments": parents, "employees": children})
    assert p["foreign_keys"] == []
    cand = next(c for c in p["foreign_key_candidates"] if c["from_column"] == "dept_id")
    assert 0.5 <= cand["overlap"] < 0.9
    assert cand["status"] == "needs_review"
    assert any("no matching parent" in r for r in cand["review_reasons"])


def test_few_values_without_a_name_are_not_accepted():
    # coupon_code values happen to equal customer_code; the name does not agree.
    customers = [{"customer_code": f"K{i:03d}", "customer_name": f"n{i}"} for i in range(1, 40)]
    orders = [{"order_id": f"O{i:05d}", "coupon_code": f"K{(i % 8) + 1:03d}"} for i in range(1, 300)]
    p = profile_tables({"customers": customers, "orders": orders})
    assert not any(f["from_column"] == "coupon_code" for f in p["foreign_keys"])
    cand = next(c for c in p["foreign_key_candidates"] if c["from_column"] == "coupon_code")
    assert cand["status"] == "needs_review"
    assert any("does not point" in r for r in cand["review_reasons"])


def test_two_distinct_values_get_a_low_support_confidence():
    plans = [{"plan_id": f"P{i}", "plan_name": f"Plan {i}"} for i in range(1, 30)]
    members = [{"member_id": f"M{i}", "plan_id": "P1" if i % 2 else "P2"} for i in range(1, 60)]
    p = profile_tables({"plans": plans, "members": members})
    fk = next(f for f in p["foreign_keys"] if f["from_column"] == "plan_id")
    assert fk["overlap"] == 1.0
    assert fk["support"] == "low"
    assert fk["confidence"] < 0.8  # Wilson, not a flat 1.0
    assert any("only 2 distinct" in w for w in p["warnings"])


def test_two_column_key_is_found():
    lines = [
        {"order_id": f"O{o:04d}", "line_no": l, "sku": f"S{o * 10 + l}"}
        for o in range(1, 201) for l in range(1, 4)
    ]
    ships = [
        {"shipment_id": f"SH{i:05d}", "order_id": r["order_id"], "line_no": r["line_no"], "qty": 1}
        for i, r in enumerate(lines[::2])
    ]
    orders = [{"order_id": f"O{o:04d}", "status": "open"} for o in range(1, 201)]
    p = profile_tables({"orders": orders, "order_lines": lines, "shipments": ships})
    assert ("shipments", ("order_id", "line_no"), "order_lines", ("order_id", "line_no")) in [
        _edge(f) for f in p["composite_foreign_keys"]
    ]
    lines_table = next(t for t in p["tables"] if t["name"] == "order_lines")
    assert ["order_id", "line_no"] in lines_table["composite_key_candidates"]


def test_accepting_a_review_candidate_moves_it_into_use():
    random.seed(3)
    customers = [{"customer_id": f"C{i:04d}", "customer_name": f"Cust {i}"} for i in range(1, 201)]
    orders = [{"order_id": f"O{i:05d}", "customer_id": f"C{random.randint(1, 200):04d}"} for i in range(1, 601)]
    for i in range(80):
        orders.append({"order_id": f"X{i:05d}", "customer_id": f"MISSING-{i}"})
    p = profile_tables({"customers": customers, "orders": orders})
    assert p["foreign_keys"] == []
    cand = p["foreign_key_candidates"][0]
    applied = apply_relationship_decisions(p, [{
        "from_table": cand["from_table"], "from_column": cand["from_column"],
        "to_table": cand["to_table"], "to_column": cand["to_column"],
        "decision": "accept", "by": "tester", "at": "2026-01-01T00:00:00Z",
    }])
    assert applied == 1
    assert len(p["foreign_keys"]) == 1
    assert p["foreign_keys"][0]["status"] == "accepted_by_review"
    assert p["summary"]["foreign_key_review_count"] == 0


def test_rejecting_a_candidate_keeps_it_out_of_use():
    parents = [{"dept_id": f"D{i}", "dept_name": f"Dept {i}"} for i in range(1, 51)]
    children = [{"emp_id": f"E{i}", "dept_id": f"D{(i % 50) + 1}"} for i in range(1, 401)]
    for i in range(20):
        children.append({"emp_id": f"X{i}", "dept_id": f"MISSING-{i}"})
    p = profile_tables({"departments": parents, "employees": children})
    cand = p["foreign_key_candidates"][0]
    apply_relationship_decisions(p, [{
        "from_table": cand["from_table"], "from_column": cand["from_column"],
        "to_table": cand["to_table"], "to_column": cand["to_column"],
        "decision": "reject", "by": "tester", "at": "2026-01-01T00:00:00Z",
    }])
    assert p["foreign_keys"] == []
    assert p["foreign_key_candidates"][0]["status"] == "rejected"
