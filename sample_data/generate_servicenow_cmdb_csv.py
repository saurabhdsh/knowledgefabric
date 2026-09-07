#!/usr/bin/env python3
"""Generate a Weave-ready ServiceNow + CMDB CSV (5,000 rows).

Designed for Database → CSV fabric upload so Knowledge Graph, Ontology discovery,
and business-rule extraction all have rich, linked ITSM/CMDB context.

Output:
  sample_data/servicenow_cmdb_itsm_5000.csv
"""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42
TOTAL_ROWS = 5000
OUT = Path(__file__).resolve().parent / "servicenow_cmdb_itsm_5000.csv"

PRIORITIES = ["1 - Critical", "2 - High", "3 - Moderate", "4 - Low"]
STATES = ["New", "In Progress", "On Hold", "Resolved", "Closed", "Canceled"]
CATEGORIES = [
    ("Software", ["Application", "OS", "Middleware", "License"]),
    ("Hardware", ["Server", "Storage", "Endpoint", "Peripheral"]),
    ("Network", ["Connectivity", "VPN", "Firewall", "DNS"]),
    ("Database", ["Performance", "Availability", "Backup", "Replication"]),
    ("Security", ["Access", "Vulnerability", "Phishing", "IAM"]),
    ("Inquiry / Help", ["How-to", "Account", "Password", "Request"]),
]
ENVIRONMENTS = ["prod", "uat", "dev", "dr"]
CI_CLASSES = [
    "Application Service",
    "Linux Server",
    "Windows Server",
    "Database Instance",
    "Load Balancer",
    "Network Gateway",
    "Mail Server",
    "Kubernetes Cluster",
    "Storage Array",
    "Virtual Machine",
]
SERVICE_TIERS = ["Tier-0", "Tier-1", "Tier-2", "Tier-3"]
CRITICALITY = ["Critical", "High", "Medium", "Low"]
DEPARTMENTS = [
    "Claims Ops",
    "Digital Claims",
    "Member Services",
    "Field Ops",
    "Finance",
    "IT Operations",
    "Security Ops",
    "Clinical Ops",
]
LOCATIONS = ["MN", "TX", "FL", "CA", "NY", "IL", "WA", "GA", "AZ", "CO"]
GROUPS = [
    ("GRP001", "Service Desk", "Alice Johnson"),
    ("GRP002", "Network Operations", "Bob Smith"),
    ("GRP003", "App Support", "Carla Gomez"),
    ("GRP004", "Database Administration", "Diego Ruiz"),
    ("GRP005", "Security Operations", "Elena Park"),
    ("GRP006", "Cloud Platform", "Farah Khan"),
    ("GRP007", "Major Incident Team", "Greg Walsh"),
    ("GRP008", "Endpoint Support", "Hannah Lee"),
]
CLOSE_CODES = [
    "Solved (Permanently)",
    "Solved (Work Around)",
    "Solved Remotely (Permanently)",
    "Not Solved (Not Reproducible)",
    "Closed/Resolved by Caller",
    "Known Error",
]
CHANGE_TYPES = ["Standard", "Normal", "Emergency"]
CHANGE_RISKS = ["Low", "Medium", "High"]

SHORT_DESCS = [
    "Email service outage affecting claims processors",
    "VPN intermittent disconnect for remote staff",
    "Claims API latency spike above SLA threshold",
    "Member portal login failures after IAM change",
    "Database CPU saturation on claims-core-db",
    "Load balancer health checks failing for payments-api",
    "Kubernetes node NotReady in prod cluster",
    "Storage array capacity warning at 92%",
    "DNS resolution failures for internal apps",
    "Firewall rule blocking provider directory sync",
    "SSO token expiry causing session drops",
    "Backup job failed for finance data mart",
    "Phishing campaign reported by Member Services",
    "Printer queue stuck in regional office",
    "Password reset workflow not sending MFA codes",
    "ServiceNow MID server heartbeat lost",
    "Redis cache eviction storm on session store",
    "Kafka consumer lag on claim-events topic",
    "TLS certificate expiring within 7 days",
    "CI discovery failing for new VMs",
]

BUSINESS_RULES = [
    "P1 incidents must be assigned to Major Incident Team within 15 minutes.",
    "Critical business services must have an active SLA and named CI owner.",
    "Production CMDB CIs must not be retired while open P1/P2 incidents reference them.",
    "Emergency changes must require CAB approval before production deployment.",
    "Incidents impacting Tier-0 services should auto-create a linked problem record.",
    "Assignment group must match CI support group for infrastructure incidents.",
    "Resolved incidents must include a close code and resolution notes.",
    "SLA breach risk must escalate to the service owner when breach probability exceeds 70%.",
    "Security category incidents must be routed to Security Operations.",
    "CMDB relationships must be validated before change implementation on dependent CIs.",
    "Caller department should be captured for every incident for operational analytics.",
    "On Hold incidents cannot remain without a work note update for more than 48 hours.",
    "Database incidents on prod instances must page Database Administration.",
    "Known Error close code should link to an existing problem record.",
    "Network gateway CIs must have documented upstream and downstream service dependencies.",
]


def _ci_pool(n: int = 180) -> list[dict]:
    cis = []
    for i in range(1, n + 1):
        cls = CI_CLASSES[i % len(CI_CLASSES)]
        env = ENVIRONMENTS[i % len(ENVIRONMENTS)]
        grp = GROUPS[i % len(GROUPS)]
        name = f"{cls.lower().replace(' ', '-')}-{env}-{i:03d}"
        cis.append(
            {
                "cmdb_ci_id": f"CI{i:04d}",
                "cmdb_ci_name": name,
                "cmdb_ci_class": cls,
                "cmdb_ci_environment": env,
                "cmdb_ci_status": "Operational" if i % 17 else "Maintenance",
                "cmdb_ci_owner": f"owner_{(i % 40) + 1:02d}",
                "cmdb_ci_support_group_id": grp[0],
                "cmdb_ci_support_group": grp[1],
                "cmdb_ci_location": LOCATIONS[i % len(LOCATIONS)],
                "cmdb_ci_install_status": "Installed",
                "cmdb_ci_business_criticality": CRITICALITY[i % len(CRITICALITY)],
            }
        )
    return cis


def _service_pool(n: int = 40) -> list[dict]:
    names = [
        "Messaging Platform",
        "Secure Access VPN",
        "Claims Core API",
        "Member Portal",
        "Provider Directory",
        "Payments Gateway",
        "Identity & Access",
        "Finance Data Mart",
        "Clinical Data Hub",
        "ServiceNow ITSM",
        "Email Collaboration",
        "Kubernetes Platform",
        "Observability Stack",
        "Backup & Recovery",
        "Customer Contact Center",
    ]
    services = []
    for i in range(1, n + 1):
        services.append(
            {
                "business_service_id": f"SVC{i:03d}",
                "business_service": f"{names[(i - 1) % len(names)]}{' ' + str(i) if i > len(names) else ''}".strip(),
                "service_criticality": CRITICALITY[i % len(CRITICALITY)],
                "service_tier": SERVICE_TIERS[i % len(SERVICE_TIERS)],
                "service_owner": f"svc_owner_{(i % 20) + 1:02d}",
            }
        )
    return services


def _user_pool(n: int = 120) -> list[dict]:
    first = ["Alex", "Jordan", "Sam", "Taylor", "Casey", "Riley", "Morgan", "Avery", "Quinn", "Jamie"]
    last = ["Nguyen", "Patel", "Garcia", "Kim", "Brown", "Davis", "Lopez", "Wilson", "Martinez", "Anderson"]
    users = []
    for i in range(1, n + 1):
        users.append(
            {
                "caller_user_id": f"USR{i:04d}",
                "caller_name": f"{first[i % len(first)]} {last[(i * 3) % len(last)]}",
                "caller_department": DEPARTMENTS[i % len(DEPARTMENTS)],
                "caller_location": LOCATIONS[i % len(LOCATIONS)],
                "caller_email": f"user{i:04d}@example.com",
            }
        )
    return users


def build_rows(total: int = TOTAL_ROWS) -> list[dict]:
    rng = random.Random(SEED)
    cis = _ci_pool()
    services = _service_pool()
    users = _user_pool()
    start = datetime(2025, 1, 1, 8, 0, 0)

    rows: list[dict] = []
    for i in range(1, total + 1):
        cat, subs = CATEGORIES[i % len(CATEGORIES)]
        sub = subs[i % len(subs)]
        priority = PRIORITIES[0 if i % 17 == 0 else 1 if i % 7 == 0 else 2 if i % 3 == 0 else 3]
        state = STATES[i % len(STATES)]
        ci = cis[i % len(cis)]
        svc = services[i % len(services)]
        user = users[i % len(users)]
        # Prefer assignment group aligned to CI support group (business rule friendly)
        if i % 5 == 0:
            grp = GROUPS[i % len(GROUPS)]
        else:
            grp = next((g for g in GROUPS if g[0] == ci["cmdb_ci_support_group_id"]), GROUPS[0])

        opened = start + timedelta(hours=i * 3 + (i % 11), minutes=(i * 7) % 60)
        resolve_hours = {PRIORITIES[0]: 4, PRIORITIES[1]: 8, PRIORITIES[2]: 24, PRIORITIES[3]: 72}[priority]
        resolved = opened + timedelta(hours=resolve_hours - (i % 3), minutes=(i * 13) % 60)
        sla_breach = "Breached" if state in {"Resolved", "Closed"} and (i % 19 == 0) else (
            "At Risk" if i % 11 == 0 else "Within SLA"
        )
        problem_id = f"PRB{(i % 80) + 1:04d}" if i % 4 == 0 or priority.startswith("1") else ""
        change_id = f"CHG{(i % 60) + 1:04d}" if state in {"Resolved", "Closed"} or i % 6 == 0 else ""
        change_type = CHANGE_TYPES[i % len(CHANGE_TYPES)] if change_id else ""
        change_risk = CHANGE_RISKS[i % len(CHANGE_RISKS)] if change_id else ""

        short = SHORT_DESCS[i % len(SHORT_DESCS)]
        rule = BUSINESS_RULES[i % len(BUSINESS_RULES)]
        description = (
            f"{short}. Impacted CI {ci['cmdb_ci_name']} ({ci['cmdb_ci_class']}) in "
            f"{ci['cmdb_ci_environment']} supports business service {svc['business_service']} "
            f"({svc['service_tier']}, criticality {svc['service_criticality']}). "
            f"Caller {user['caller_name']} from {user['caller_department']}. "
            f"Business rule: {rule}"
        )

        # Explicit relationship narrative for KG / ontology extraction
        relationship_summary = (
            f"Incident INC{i:07d} reported_by {user['caller_user_id']}; "
            f"assigned_to_group {grp[0]}; impacts_ci {ci['cmdb_ci_id']}; "
            f"impacts_service {svc['business_service_id']}"
        )
        if problem_id:
            relationship_summary += f"; linked_problem {problem_id}"
        if change_id:
            relationship_summary += f"; resolved_by_change {change_id}"

        # Parent/child CI dependency hints for CMDB ontology
        parent_ci = cis[(i + 17) % len(cis)]["cmdb_ci_id"]
        depends_on_ci = cis[(i + 41) % len(cis)]["cmdb_ci_id"]

        rows.append(
            {
                "record_type": "servicenow_incident",
                "incident_number": f"INC{i:07d}",
                "short_description": short,
                "description": description,
                "priority": priority,
                "urgency": str((i % 3) + 1),
                "impact": str((i % 3) + 1),
                "state": state,
                "category": cat,
                "subcategory": sub,
                "opened_at": opened.isoformat() + "Z",
                "resolved_at": resolved.isoformat() + "Z" if state in {"Resolved", "Closed"} else "",
                "close_code": CLOSE_CODES[i % len(CLOSE_CODES)] if state in {"Resolved", "Closed"} else "",
                "close_notes": (
                    f"Resolved via {change_type or 'standard'} remediation on {ci['cmdb_ci_name']}."
                    if state in {"Resolved", "Closed"}
                    else ""
                ),
                "caller_user_id": user["caller_user_id"],
                "caller_name": user["caller_name"],
                "caller_department": user["caller_department"],
                "caller_location": user["caller_location"],
                "caller_email": user["caller_email"],
                "assignment_group_id": grp[0],
                "assignment_group": grp[1],
                "assignment_group_manager": grp[2],
                "assigned_to": f"tech_{(i % 35) + 1:02d}",
                "cmdb_ci_id": ci["cmdb_ci_id"],
                "cmdb_ci_name": ci["cmdb_ci_name"],
                "cmdb_ci_class": ci["cmdb_ci_class"],
                "cmdb_ci_environment": ci["cmdb_ci_environment"],
                "cmdb_ci_status": ci["cmdb_ci_status"],
                "cmdb_ci_owner": ci["cmdb_ci_owner"],
                "cmdb_ci_support_group_id": ci["cmdb_ci_support_group_id"],
                "cmdb_ci_support_group": ci["cmdb_ci_support_group"],
                "cmdb_ci_location": ci["cmdb_ci_location"],
                "cmdb_ci_install_status": ci["cmdb_ci_install_status"],
                "cmdb_ci_business_criticality": ci["cmdb_ci_business_criticality"],
                "cmdb_parent_ci_id": parent_ci,
                "cmdb_depends_on_ci_id": depends_on_ci,
                "business_service_id": svc["business_service_id"],
                "business_service": svc["business_service"],
                "service_criticality": svc["service_criticality"],
                "service_tier": svc["service_tier"],
                "service_owner": svc["service_owner"],
                "related_problem_id": problem_id,
                "related_change_id": change_id,
                "change_type": change_type,
                "change_risk": change_risk,
                "sla_id": "SLA001" if priority.startswith("1") else "SLA002" if priority.startswith("2") else "SLA003",
                "sla_name": (
                    "P1 Resolution SLA"
                    if priority.startswith("1")
                    else "P2 Resolution SLA"
                    if priority.startswith("2")
                    else "Standard Resolution SLA"
                ),
                "sla_target_hours": resolve_hours,
                "sla_breach_status": sla_breach,
                "business_rule_id": f"BR{(i % len(BUSINESS_RULES)) + 1:03d}",
                "business_rule_text": rule,
                "relationship_summary": relationship_summary,
                "knowledge_domain": "itsm_cmdb",
                "data_source": "synthetic_servicenow_cmdb_weave",
                "row_id": i,
            }
        )

        # Light deterministic shuffle of priority/state already applied; keep RNG used for realism hooks
        _ = rng.random()
    return rows


def main() -> None:
    rows = build_rows(TOTAL_ROWS)
    fieldnames = list(rows[0].keys())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows → {OUT}")
    print(f"Columns ({len(fieldnames)}): {', '.join(fieldnames[:12])} ...")


if __name__ == "__main__":
    main()
