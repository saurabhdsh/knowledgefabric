#!/usr/bin/env python3
"""Seed workspace.claims_demo on Databricks for Weave fabric demos.

Credentials via env (never commit tokens):
  DATABRICKS_HOST=dbc-xxxx.cloud.databricks.com
  DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/<warehouse_id>
  DATABRICKS_TOKEN=<PAT with sql scope / All APIs>

Usage:
  export DATABRICKS_HOST=...
  export DATABRICKS_HTTP_PATH=...
  export DATABRICKS_TOKEN=...
  python scripts/seed_databricks_claims_demo.py
"""
from __future__ import annotations

import os
import random
import sys
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from databricks import sql

HOST = os.environ.get("DATABRICKS_HOST", "").replace("https://", "").replace("http://", "").strip().strip("/")
HTTP_PATH = os.environ.get("DATABRICKS_HTTP_PATH", "").strip()
TOKEN = os.environ.get("DATABRICKS_TOKEN", "").strip()
SCHEMA = "workspace.claims_demo"

PLANS = [
    ("PLN_GOLD", "Gold PPO Plus", "PPO", "Northwind Health", "Tier1", 1500, 6000),
    ("PLN_SILVER", "Silver HMO Care", "HMO", "Northwind Health", "Tier2", 2500, 8000),
    ("PLN_BRONZE", "Bronze EPO Essentials", "EPO", "Summit Mutual", "Tier3", 4000, 9100),
    ("PLN_CSNP", "Chronic SNP Advantage", "Medicare Advantage", "Summit Mutual", "Tier1", 0, 3500),
]

SPECIALTIES = [
    ("Primary Care", "Physician"),
    ("Cardiology", "Physician"),
    ("Orthopedics", "Physician"),
    ("Emergency Medicine", "Facility"),
    ("Laboratory", "Ancillary"),
    ("Radiology", "Ancillary"),
    ("Physical Therapy", "Ancillary"),
    ("Behavioral Health", "Physician"),
]

DIAGNOSES = [
    ("I10", "Essential hypertension", "Cardiovascular", True),
    ("E11.9", "Type 2 diabetes mellitus", "Endocrine", True),
    ("J06.9", "Acute upper respiratory infection", "Respiratory", False),
    ("M54.5", "Low back pain", "Musculoskeletal", False),
    ("F32.9", "Major depressive disorder", "Behavioral", True),
    ("N39.0", "Urinary tract infection", "Genitourinary", False),
    ("K21.9", "GERD", "Digestive", True),
    ("R07.9", "Chest pain unspecified", "Cardiovascular", False),
    ("S93.4", "Ankle sprain", "Injury", False),
    ("Z00.00", "General adult exam", "Preventive", False),
]

PROCEDURES = [
    ("99213", "Office visit established level 3", "E&M", 185),
    ("99214", "Office visit established level 4", "E&M", 265),
    ("99285", "ED visit high severity", "Emergency", 1450),
    ("93000", "Electrocardiogram", "Cardiology", 95),
    ("80053", "Comprehensive metabolic panel", "Lab", 48),
    ("71046", "Chest X-ray 2 views", "Imaging", 120),
    ("97110", "Therapeutic exercises", "Therapy", 85),
    ("90834", "Psychotherapy 45 min", "Behavioral", 160),
    ("27447", "Total knee arthroplasty", "Surgery", 18500),
    ("36415", "Venipuncture", "Lab", 22),
]

FIRST = ["Ava", "Noah", "Mia", "Liam", "Emma", "Olivia", "Ethan", "Sophia", "Lucas", "Isabella",
         "Mason", "Amelia", "Logan", "Harper", "James", "Evelyn", "Benjamin", "Charlotte", "Henry", "Luna"]
LAST = ["Nguyen", "Patel", "Garcia", "Kim", "Johnson", "Williams", "Brown", "Davis", "Miller", "Wilson",
        "Moore", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin", "Thompson", "Lee"]
STATES = ["CA", "TX", "NY", "FL", "IL", "WA", "MA", "GA", "NC", "AZ"]
STATUSES = ["Paid", "Paid", "Paid", "Approved", "Pending", "Denied", "Under Review"]
CLAIM_TYPES = ["Professional", "Institutional", "Pharmacy", "Dental"]
POS = ["Office", "Outpatient Hospital", "Inpatient Hospital", "Emergency Room", "Telehealth"]


def money(n: float) -> str:
    return f"{Decimal(str(round(n, 2)))}"


def ensure_env() -> None:
    missing = [k for k, v in {
        "DATABRICKS_HOST": HOST,
        "DATABRICKS_HTTP_PATH": HTTP_PATH,
        "DATABRICKS_TOKEN": TOKEN,
    }.items() if not v]
    if missing:
        raise SystemExit(f"Missing env: {', '.join(missing)}")


def run(cur, statement: str) -> None:
    cur.execute(statement)


def seed(cur) -> None:
    ddl_path = os.path.join(os.path.dirname(__file__), "databricks_claims_demo.sql")
    with open(ddl_path, encoding="utf-8") as f:
        ddl = f.read()
    # Split on semicolons; skip comments-only chunks
    for chunk in ddl.split(";"):
        stmt = "\n".join(
            line for line in chunk.splitlines()
            if line.strip() and not line.strip().startswith("--")
        ).strip()
        if stmt:
            print(f"DDL: {stmt.splitlines()[0][:80]}...")
            run(cur, stmt)

    rng = random.Random(42)
    today = date.today()

    # plans
    for plan_id, name, ptype, carrier, tier, ded, oop in PLANS:
        run(cur, f"""
        INSERT INTO {SCHEMA}.plans VALUES (
          '{plan_id}', '{name}', '{ptype}', '{carrier}', '{tier}',
          {money(ded)}, {money(oop)}, DATE '2024-01-01', DATE '2026-12-31'
        )
        """)

    # diagnosis / procedure dims
    for code, desc, cat, chronic in DIAGNOSES:
        run(cur, f"""
        INSERT INTO {SCHEMA}.diagnosis_codes VALUES (
          '{code}', '{desc.replace("'", "''")}', '{cat}', {str(chronic).lower()}
        )
        """)
    for code, desc, cat, avg in PROCEDURES:
        run(cur, f"""
        INSERT INTO {SCHEMA}.procedure_codes VALUES (
          '{code}', '{desc.replace("'", "''")}', '{cat}', {money(avg)}
        )
        """)

    providers = []
    for i in range(1, 26):
        pid = f"PRV_{i:04d}"
        spec, ptype = SPECIALTIES[(i - 1) % len(SPECIALTIES)]
        providers.append(pid)
        run(cur, f"""
        INSERT INTO {SCHEMA}.providers VALUES (
          '{pid}', '{1000000000 + i}', 'CareCenter {spec} {i}',
          '{spec}', '{ptype}', 'Metro', '{rng.choice(STATES)}',
          '{10_000_000 + i}', '{rng.choice(["In Network", "In Network", "Out of Network"])}'
        )
        """)

    members = []
    for i in range(1, 81):
        mid = f"MBR_{i:04d}"
        members.append(mid)
        plan_id = PLANS[(i - 1) % len(PLANS)][0]
        dob = date(1955, 1, 1) + timedelta(days=rng.randint(0, 18000))
        enroll = date(2023, 1, 1) + timedelta(days=rng.randint(0, 600))
        run(cur, f"""
        INSERT INTO {SCHEMA}.members VALUES (
          '{mid}', 'MEM{100000 + i}', '{rng.choice(FIRST)}', '{rng.choice(LAST)}',
          DATE '{dob.isoformat()}', '{rng.choice(["F", "M", "X"])}',
          'member{i}@example.com', '555-{1000+i:04d}',
          '{rng.choice(STATES)}', '{90000 + i}',
          '{plan_id}', DATE '{enroll.isoformat()}',
          '{rng.choice(["Active", "Active", "Active", "Terminated"])}',
          {round(rng.uniform(0.2, 4.8), 2)}
        )
        """)

    claim_count = 220
    for i in range(1, claim_count + 1):
        cid = f"CLM_{i:05d}"
        member_id = members[(i - 1) % len(members)]
        provider_id = providers[(i * 3) % len(providers)]
        # member plan_id lookup approximate from index
        plan_id = PLANS[((i - 1) % len(members)) % len(PLANS)][0]
        dx = DIAGNOSES[(i - 1) % len(DIAGNOSES)][0]
        svc = today - timedelta(days=rng.randint(5, 400))
        status = STATUSES[rng.randint(0, len(STATUSES) - 1)]
        billed = round(rng.uniform(120, 22000), 2)
        allowed = round(billed * rng.uniform(0.45, 0.92), 2)
        paid = 0.0 if status in ("Denied", "Pending", "Under Review") else round(allowed * rng.uniform(0.7, 0.95), 2)
        member_resp = round(max(0, allowed - paid), 2) if status == "Paid" else round(allowed * 0.2, 2)
        denial = "Medical necessity not met" if status == "Denied" else ""
        ctype = CLAIM_TYPES[(i - 1) % len(CLAIM_TYPES)]
        pos = POS[(i - 1) % len(POS)]
        run(cur, f"""
        INSERT INTO {SCHEMA}.claims VALUES (
          '{cid}', 'CN{202400000 + i}', '{member_id}', '{provider_id}', '{plan_id}',
          '{dx}', DATE '{svc.isoformat()}', DATE '{(svc + timedelta(days=rng.randint(0, 3))).isoformat()}',
          DATE '{(svc + timedelta(days=rng.randint(1, 10))).isoformat()}',
          '{status}', '{ctype}', '{pos}',
          {money(billed)}, {money(allowed)}, {money(paid)}, {money(member_resp)},
          '{denial.replace("'", "''")}'
        )
        """)

        lines = rng.randint(1, 4)
        for ln in range(1, lines + 1):
            proc = PROCEDURES[(i + ln) % len(PROCEDURES)]
            line_billed = round(billed / lines, 2)
            line_allowed = round(allowed / lines, 2)
            line_paid = round(paid / lines, 2)
            lid = f"CLL_{i:05d}_{ln}"
            run(cur, f"""
            INSERT INTO {SCHEMA}.claim_lines VALUES (
              '{lid}', '{cid}', {ln}, '{proc[0]}', '{dx}',
              DATE '{svc.isoformat()}', {rng.randint(1, 3)},
              {money(line_billed)}, {money(line_allowed)}, {money(line_paid)},
              '{status}'
            )
            """)

        if paid > 0:
            pay_id = f"PAY_{i:05d}"
            pay_date = svc + timedelta(days=rng.randint(10, 45))
            run(cur, f"""
            INSERT INTO {SCHEMA}.payments VALUES (
              '{pay_id}', '{cid}', DATE '{pay_date.isoformat()}',
              '{rng.choice(["EFT", "Check", "EFT"])}', 'EFT{900000 + i}',
              {money(paid)}, '{provider_id}'
            )
            """)

        # lifecycle events
        events = [
            ("Submitted", "provider_portal", "Claim received from provider"),
            ("Adjudicated", "claims_engine", f"Status set to {status}"),
        ]
        if status == "Paid":
            events.append(("PaymentIssued", "finance", "Payment released to provider"))
        if status == "Denied":
            events.append(("Denied", "medical_review", "Denial letter generated"))
        for ei, (etype, actor, notes) in enumerate(events, start=1):
            ts = datetime.combine(svc, datetime.min.time()) + timedelta(days=ei, hours=ei)
            run(cur, f"""
            INSERT INTO {SCHEMA}.claim_events VALUES (
              'EVT_{i:05d}_{ei}', '{cid}', TIMESTAMP '{ts.isoformat(sep=" ")}',
              '{etype}', '{actor}', '{notes.replace("'", "''")}'
            )
            """)

    # counts
    for table in ("members", "plans", "providers", "claims", "claim_lines", "payments", "claim_events",
                  "diagnosis_codes", "procedure_codes"):
        cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.{table}")
        print(f"{table}: {cur.fetchone()[0]} rows")


def main() -> int:
    ensure_env()
    print(f"Connecting to {HOST} {HTTP_PATH}")
    with sql.connect(server_hostname=HOST, http_path=HTTP_PATH, access_token=TOKEN) as conn:
        with conn.cursor() as cur:
            seed(cur)
    print("Done. Use Weave Create Knowledge → Databricks with:")
    print(f"  server_hostname = {HOST}")
    print(f"  warehouse_id / http_path = {HTTP_PATH}")
    print(f"  catalog = workspace")
    print(f"  schema  = claims_demo")
    print("  tables  = claims (or members / claim_lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
