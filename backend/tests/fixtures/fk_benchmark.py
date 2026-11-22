"""Synthetic schemas with declared foreign keys, used to score key discovery.

Each schema is a small stand-in for a public database: tables of rows, plus the
links that a DBA would have declared. The discovery test is scored against that
declared set — found, missed, and wrong.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Set, Tuple


Edge = Tuple[str, str, str, str]  # (from_table, from_column, to_table, to_column)


def _edge(from_table: str, from_column: str, to_table: str, to_column: str) -> Edge:
    return (from_table, from_column, to_table, to_column)


def healthcare_cost_of_care(seed: int = 7) -> Dict[str, Any]:
    """Members, plans, providers, claims — the fabric Weave demos most often."""
    rng = random.Random(seed)
    plans = [{"plan_id": f"PLN-{c}", "plan_name": name, "premium": premium}
             for c, name, premium in (("A", "Gold", "1180.00"), ("B", "Silver", "940.50"), ("C", "Bronze", "720.00"))]
    providers = [{"provider_id": f"PRV-{i:03d}", "provider_name": f"Clinic {i}", "npi": f"1{i:09d}"}
                 for i in range(1, 41)]
    members = []
    for i in range(1, 301):
        members.append({
            "member_id": f"MEM-{i:04d}",
            "member_name": f"Person {i}",
            "plan_id": plans[i % 3]["plan_id"],
            "pcp_provider_id": providers[i % 40]["provider_id"],
            "dob": f"19{50 + i % 40}-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
            "age": 30 + (i % 50),
        })
    claims = []
    for i in range(1, 901):
        m = members[i % 300]
        claims.append({
            "claim_id": f"CLM-{i:05d}",
            "member_id": m["member_id"],
            "provider_id": providers[rng.randint(0, 39)]["provider_id"],
            "service_date": f"2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
            "paid_amount": f"{(i % 40) * 25 + 50}.00",
            "claim_type": ["Inpatient", "Outpatient", "ER"][i % 3],
        })
    return {
        "name": "healthcare_cost_of_care",
        "tables": {"plans": plans, "providers": providers, "members": members, "claims": claims},
        "declared": {
            _edge("members", "plan_id", "plans", "plan_id"),
            _edge("members", "pcp_provider_id", "providers", "provider_id"),
            _edge("claims", "member_id", "members", "member_id"),
            _edge("claims", "provider_id", "providers", "provider_id"),
        },
        # Columns that look numeric and must never be treated as keys.
        "forbidden": {("members", "age"), ("claims", "paid_amount")},
    }


def retail_orders(seed: int = 11) -> Dict[str, Any]:
    """Customers, products, orders, and order lines with a two-column line key."""
    rng = random.Random(seed)
    customers = [{"customer_id": f"C{i:04d}", "customer_name": f"Customer {i}", "city": f"City {i % 20}"}
                 for i in range(1, 201)]
    products = [{"product_id": f"P{i:04d}", "product_name": f"Product {i}", "unit_price": 5 + i % 40}
                for i in range(1, 101)]
    orders = [{"order_id": f"O{i:05d}", "customer_id": customers[rng.randint(0, 199)]["customer_id"],
               "order_date": f"2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}", "status": "open"}
              for i in range(1, 501)]
    lines = []
    for order in orders:
        for line_no in range(1, rng.randint(2, 5)):
            lines.append({
                "order_id": order["order_id"],
                "line_no": line_no,
                "product_id": products[rng.randint(0, 99)]["product_id"],
                "quantity": rng.randint(1, 6),
            })
    return {
        "name": "retail_orders",
        "tables": {"customers": customers, "products": products, "orders": orders, "order_lines": lines},
        "declared": {
            _edge("orders", "customer_id", "customers", "customer_id"),
            _edge("order_lines", "order_id", "orders", "order_id"),
            _edge("order_lines", "product_id", "products", "product_id"),
        },
        "declared_composite": {
            (("order_lines", ("order_id", "line_no")), ("orders", ("order_id",))),  # not declared — line points at order only
        },
        "forbidden": {("order_lines", "quantity"), ("products", "unit_price")},
    }


def itsm_incidents(seed: int = 19) -> Dict[str, Any]:
    """Incidents, callers, assignment groups, and related CIs."""
    rng = random.Random(seed)
    groups = [{"group_id": f"G{i:03d}", "group_name": f"Group {i}"} for i in range(1, 21)]
    callers = [{"caller_id": f"U{i:04d}", "caller_name": f"User {i}", "email": f"u{i}@example.com"}
               for i in range(1, 151)]
    cis = [{"ci_id": f"CI{i:04d}", "ci_name": f"Server {i}"} for i in range(1, 81)]
    incidents = []
    for i in range(1, 401):
        incidents.append({
            "incident_id": f"INC{i:06d}",
            "caller_id": callers[rng.randint(0, 149)]["caller_id"],
            "assignment_group_id": groups[rng.randint(0, 19)]["group_id"],
            "ci_id": cis[rng.randint(0, 79)]["ci_id"],
            "priority": (i % 4) + 1,
            "short_description": f"Issue {i}",
        })
    return {
        "name": "itsm_incidents",
        "tables": {"groups": groups, "callers": callers, "configuration_items": cis, "incidents": incidents},
        "declared": {
            _edge("incidents", "caller_id", "callers", "caller_id"),
            _edge("incidents", "assignment_group_id", "groups", "group_id"),
            _edge("incidents", "ci_id", "configuration_items", "ci_id"),
        },
        "forbidden": {("incidents", "priority")},
    }


def noisy_lookalikes(seed: int = 23) -> Dict[str, Any]:
    """A schema where value inclusion alone would invent a wrong link.

    ``coupon_code`` values happen to equal ``customer_code``, but the column is
    not a customer reference. Discovery must leave it out of the accepted set.
    """
    rng = random.Random(seed)
    customers = [{"customer_code": f"K{i:03d}", "customer_name": f"Cust {i}"} for i in range(1, 41)]
    coupons = [{"coupon_code": f"K{i:03d}", "discount_pct": i % 20} for i in range(1, 21)]
    orders = [{"order_id": f"O{i:05d}", "customer_code": customers[rng.randint(0, 39)]["customer_code"],
               "coupon_code": coupons[rng.randint(0, 19)]["coupon_code"]}
              for i in range(1, 301)]
    return {
        "name": "noisy_lookalikes",
        "tables": {"customers": customers, "coupons": coupons, "orders": orders},
        "declared": {
            _edge("orders", "customer_code", "customers", "customer_code"),
            _edge("orders", "coupon_code", "coupons", "coupon_code"),
        },
        # The false reading orders.coupon_code → customers.customer_code must never be accepted.
        "forbidden_links": {_edge("orders", "coupon_code", "customers", "customer_code")},
    }


ALL_SCHEMAS = [
    healthcare_cost_of_care,
    retail_orders,
    itsm_incidents,
    noisy_lookalikes,
]


def score_discovery(declared: Set[Edge], found: Set[Edge]) -> Dict[str, Any]:
    true_pos = declared & found
    false_pos = found - declared
    false_neg = declared - found
    precision = len(true_pos) / len(found) if found else 1.0
    recall = len(true_pos) / len(declared) if declared else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "found": sorted(found),
        "declared": sorted(declared),
        "true_positives": sorted(true_pos),
        "false_positives": sorted(false_pos),
        "false_negatives": sorted(false_neg),
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }
