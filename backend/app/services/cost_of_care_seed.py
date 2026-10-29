"""Synthetic Cost of Care fabric seed for care-management agents.

Builds a referential CSNP-style population with 500+ members, centered on the
Lisa COPD high-cost journey (exacerbations, ER, pharmacy, care plan, SDOH).
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Tuple


LISA_MEMBER_ID = "MEM-LISA-COPD"
LISA_NAME = "Lisa Chen"
MEMBER_COUNT = 520


def _pick(rng: random.Random, items: List[Any]) -> Any:
    return items[rng.randrange(len(items))]


def build_cost_of_care_rows(seed: int = 42) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Return (rows, connection_info) ready for process_database_data + persist."""
    rng = random.Random(seed)

    plans = [
        {"plan_id": "PLN-CSNP-GOLD", "plan_name": "CSNP Gold COPD Focus", "coverage_type": "CSNP", "network_id": "NET-PULM", "pmpm": 1180},
        {"plan_id": "PLN-CSNP-SILVER", "plan_name": "CSNP Silver Dual", "coverage_type": "CSNP", "network_id": "NET-CORE", "pmpm": 940},
        {"plan_id": "PLN-DUAL-PLUS", "plan_name": "Dual Care Plus", "coverage_type": "Dual", "network_id": "NET-CORE", "pmpm": 1025},
        {"plan_id": "PLN-WELLNESS", "plan_name": "Wellness Plus MA", "coverage_type": "MA", "network_id": "NET-COMM", "pmpm": 780},
        {"plan_id": "PLN-BASIC", "plan_name": "MA Basic", "coverage_type": "MA", "network_id": "NET-COMM", "pmpm": 640},
        {"plan_id": "PLN-CARDIAC", "plan_name": "Cardiac CSNP Elite", "coverage_type": "CSNP", "network_id": "NET-CARD", "pmpm": 1210},
        {"plan_id": "PLN-DIABETES", "plan_name": "Diabetes CSNP Care", "coverage_type": "CSNP", "network_id": "NET-ENDO", "pmpm": 1090},
        {"plan_id": "PLN-CKD", "plan_name": "CKD Continuum", "coverage_type": "CSNP", "network_id": "NET-NEPH", "pmpm": 1150},
    ]

    providers = [
        {"provider_id": "PRV-PULM-01", "provider_name": "Lakeside Pulmonology", "npi": "1457382910", "specialty": "Pulmonology", "network_id": "NET-PULM"},
        {"provider_id": "PRV-PCP-01", "provider_name": "Riverbend Family Clinic", "npi": "1982736450", "specialty": "Primary Care", "network_id": "NET-CORE"},
        {"provider_id": "PRV-ER-01", "provider_name": "Metro General ER", "npi": "1678493021", "specialty": "Emergency Medicine", "network_id": "NET-CORE"},
        {"provider_id": "PRV-HOSP-01", "provider_name": "Northshore Medical Center", "npi": "1345678901", "specialty": "Inpatient Hospital", "network_id": "NET-CORE"},
        {"provider_id": "PRV-CARD-01", "provider_name": "Summit Cardiology", "npi": "1567890123", "specialty": "Cardiology", "network_id": "NET-CARD"},
        {"provider_id": "PRV-ENDO-01", "provider_name": "Clearview Endocrinology", "npi": "1789012345", "specialty": "Endocrinology", "network_id": "NET-ENDO"},
        {"provider_id": "PRV-NEPH-01", "provider_name": "Valley Nephrology", "npi": "1890123456", "specialty": "Nephrology", "network_id": "NET-NEPH"},
        {"provider_id": "PRV-RX-01", "provider_name": "CarePath Specialty Pharmacy", "npi": "1901234567", "specialty": "Pharmacy", "network_id": "NET-CORE"},
        {"provider_id": "PRV-HH-01", "provider_name": "Harbor Home Health", "npi": "1012345678", "specialty": "Home Health", "network_id": "NET-PULM"},
        {"provider_id": "PRV-RESP-01", "provider_name": "BreathEasy Respiratory", "npi": "1123456789", "specialty": "Respiratory Therapy", "network_id": "NET-PULM"},
    ]
    # Expand provider roster for graph density
    for i in range(20):
        providers.append(
            {
                "provider_id": f"PRV-GEN-{i+1:02d}",
                "provider_name": f"Community Care Center {i+1}",
                "npi": f"2{i:09d}",
                "specialty": _pick(rng, ["Primary Care", "Internal Medicine", "Urgent Care", "Behavioral Health"]),
                "network_id": _pick(rng, ["NET-CORE", "NET-COMM", "NET-PULM"]),
            }
        )

    care_managers = [
        {"care_manager_id": "CM-01", "care_manager_name": "Maya Ortiz", "panel": "COPD High Cost", "phone": "612-555-0144"},
        {"care_manager_id": "CM-02", "care_manager_name": "Jordan Blake", "panel": "CHF / Cardiac", "phone": "612-555-0188"},
        {"care_manager_id": "CM-03", "care_manager_name": "Priya Nair", "panel": "Diabetes / CKD", "phone": "612-555-0192"},
        {"care_manager_id": "CM-04", "care_manager_name": "Sam Okonkwo", "panel": "Dual Eligible", "phone": "612-555-0117"},
    ]

    conditions = [
        ("COPD", "J44.9"),
        ("CHF", "I50.9"),
        ("Diabetes", "E11.9"),
        ("CKD", "N18.3"),
        ("Hypertension", "I10"),
        ("Depression", "F32.9"),
        ("Asthma", "J45.909"),
    ]
    states = ["MN", "WI", "IA", "ND", "SD", "IL", "MI"]
    risk_tiers = ["low", "moderate", "high", "rising_risk"]
    first_names = [
        "Ava", "Noah", "Mia", "Liam", "Emma", "Oliver", "Sophia", "Ethan", "Isabella", "Lucas",
        "Amelia", "Mason", "Harper", "Elijah", "Evelyn", "James", "Abigail", "Benjamin", "Emily", "Henry",
        "Grace", "Daniel", "Chloe", "Michael", "Lily", "David", "Zoe", "Joseph", "Nora", "Samuel",
    ]
    last_names = [
        "Thompson", "Patel", "Nguyen", "Garcia", "Johnson", "Williams", "Brown", "Davis", "Miller", "Wilson",
        "Moore", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin", "Clark", "Lewis",
        "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Green", "Adams",
    ]

    rows: List[Dict[str, Any]] = []

    # Static dims
    for plan in plans:
        rows.append({"record_type": "plan", **{k: str(v) for k, v in plan.items()}})
    for provider in providers:
        rows.append({"record_type": "provider", **provider})
    for cm in care_managers:
        rows.append({"record_type": "care_manager", **cm})

    # Lisa COPD hero case — intentionally rich for agents
    lisa = {
        "record_type": "member",
        "member_id": LISA_MEMBER_ID,
        "member_name": LISA_NAME,
        "dob": "1968-03-14",
        "age": "58",
        "gender": "F",
        "state": "MN",
        "county": "Hennepin",
        "plan_id": "PLN-CSNP-GOLD",
        "risk_tier": "high",
        "primary_condition": "COPD",
        "icd10": "J44.9",
        "secondary_conditions": "CHF;Depression;Tobacco use disorder",
        "eligibility_status": "Eligible",
        "enrollment_status": "Active",
        "ytd_medical_cost": "48750.40",
        "ytd_rx_cost": "6120.15",
        "ytd_total_cost": "54870.55",
        "pmpm_cost": "4572.55",
        "er_visits_12m": "4",
        "inpatient_admits_12m": "2",
        "readmission_flag": "true",
        "care_manager_id": "CM-01",
        "pcp_provider_id": "PRV-PCP-01",
        "specialist_provider_id": "PRV-PULM-01",
        "case_narrative": (
            "Lisa Chen is a CSNP Gold member with moderate-severe COPD and recent "
            "exacerbations. She had two inpatient stays and four ER visits in 12 months, "
            "with rising inhaler gaps and home oxygen needs. Cost-of-care agents should "
            "prioritize exacerbation prevention, medication adherence, and transportation support."
        ),
        "agent_focus": "cost_of_care|copd_exacerbation|avoidable_er|medication_adherence",
    }
    rows.append(lisa)

    lisa_diagnoses = [
        {"diagnosis_id": "DX-LISA-01", "member_id": LISA_MEMBER_ID, "icd10": "J44.9", "diagnosis_name": "COPD unspecified", "onset_date": "2019-06-01", "status": "active", "severity": "primary"},
        {"diagnosis_id": "DX-LISA-02", "member_id": LISA_MEMBER_ID, "icd10": "J44.1", "diagnosis_name": "COPD with acute exacerbation", "onset_date": "2026-01-18", "status": "recent", "severity": "exacerbation"},
        {"diagnosis_id": "DX-LISA-03", "member_id": LISA_MEMBER_ID, "icd10": "I50.9", "diagnosis_name": "Heart failure unspecified", "onset_date": "2022-11-03", "status": "active", "severity": "comorbid"},
        {"diagnosis_id": "DX-LISA-04", "member_id": LISA_MEMBER_ID, "icd10": "F32.9", "diagnosis_name": "Major depressive disorder", "onset_date": "2024-04-12", "status": "active", "severity": "comorbid"},
        {"diagnosis_id": "DX-LISA-05", "member_id": LISA_MEMBER_ID, "icd10": "Z99.81", "diagnosis_name": "Dependence on supplemental oxygen", "onset_date": "2025-09-20", "status": "active", "severity": "support"},
    ]
    for dx in lisa_diagnoses:
        rows.append({"record_type": "diagnosis", **dx})

    lisa_claims = [
        {"claim_id": "CLM-LISA-IP-01", "member_id": LISA_MEMBER_ID, "plan_id": "PLN-CSNP-GOLD", "provider_id": "PRV-HOSP-01", "service_date": "2026-01-18", "claim_type": "Inpatient", "procedure_code": "99223", "diagnosis_code": "J44.1", "allowed_amount": "18450.00", "paid_amount": "17210.00", "claim_status": "paid", "cost_driver": "COPD exacerbation admission"},
        {"claim_id": "CLM-LISA-IP-02", "member_id": LISA_MEMBER_ID, "plan_id": "PLN-CSNP-GOLD", "provider_id": "PRV-HOSP-01", "service_date": "2025-11-02", "claim_type": "Inpatient", "procedure_code": "99222", "diagnosis_code": "J44.1", "allowed_amount": "15220.00", "paid_amount": "14100.00", "claim_status": "paid", "cost_driver": "COPD exacerbation admission"},
        {"claim_id": "CLM-LISA-ER-01", "member_id": LISA_MEMBER_ID, "plan_id": "PLN-CSNP-GOLD", "provider_id": "PRV-ER-01", "service_date": "2026-02-09", "claim_type": "ER", "procedure_code": "99285", "diagnosis_code": "J44.1", "allowed_amount": "2860.00", "paid_amount": "2510.00", "claim_status": "paid", "cost_driver": "Avoidable ER - dyspnea"},
        {"claim_id": "CLM-LISA-ER-02", "member_id": LISA_MEMBER_ID, "plan_id": "PLN-CSNP-GOLD", "provider_id": "PRV-ER-01", "service_date": "2025-12-14", "claim_type": "ER", "procedure_code": "99284", "diagnosis_code": "J44.9", "allowed_amount": "2140.00", "paid_amount": "1980.00", "claim_status": "paid", "cost_driver": "Avoidable ER - dyspnea"},
        {"claim_id": "CLM-LISA-ER-03", "member_id": LISA_MEMBER_ID, "plan_id": "PLN-CSNP-GOLD", "provider_id": "PRV-ER-01", "service_date": "2025-10-03", "claim_type": "ER", "procedure_code": "99284", "diagnosis_code": "J44.9", "allowed_amount": "2055.00", "paid_amount": "1890.00", "claim_status": "paid", "cost_driver": "Avoidable ER - dyspnea"},
        {"claim_id": "CLM-LISA-ER-04", "member_id": LISA_MEMBER_ID, "plan_id": "PLN-CSNP-GOLD", "provider_id": "PRV-ER-01", "service_date": "2025-08-21", "claim_type": "ER", "procedure_code": "99283", "diagnosis_code": "J44.9", "allowed_amount": "1680.00", "paid_amount": "1520.00", "claim_status": "paid", "cost_driver": "Avoidable ER - dyspnea"},
        {"claim_id": "CLM-LISA-PCP-01", "member_id": LISA_MEMBER_ID, "plan_id": "PLN-CSNP-GOLD", "provider_id": "PRV-PCP-01", "service_date": "2026-03-01", "claim_type": "PCP", "procedure_code": "99214", "diagnosis_code": "J44.9", "allowed_amount": "185.00", "paid_amount": "148.00", "claim_status": "paid", "cost_driver": "Care coordination visit"},
        {"claim_id": "CLM-LISA-PULM-01", "member_id": LISA_MEMBER_ID, "plan_id": "PLN-CSNP-GOLD", "provider_id": "PRV-PULM-01", "service_date": "2026-02-20", "claim_type": "Specialist", "procedure_code": "99215", "diagnosis_code": "J44.9", "allowed_amount": "310.00", "paid_amount": "260.00", "claim_status": "paid", "cost_driver": "Pulmonology follow-up"},
        {"claim_id": "CLM-LISA-HH-01", "member_id": LISA_MEMBER_ID, "plan_id": "PLN-CSNP-GOLD", "provider_id": "PRV-HH-01", "service_date": "2026-01-28", "claim_type": "Home Health", "procedure_code": "G0299", "diagnosis_code": "J44.9", "allowed_amount": "940.00", "paid_amount": "880.00", "claim_status": "paid", "cost_driver": "Post-discharge home health"},
        {"claim_id": "CLM-LISA-RESP-01", "member_id": LISA_MEMBER_ID, "plan_id": "PLN-CSNP-GOLD", "provider_id": "PRV-RESP-01", "service_date": "2026-02-02", "claim_type": "DME", "procedure_code": "E1390", "diagnosis_code": "Z99.81", "allowed_amount": "420.00", "paid_amount": "390.00", "claim_status": "paid", "cost_driver": "Home oxygen"},
    ]
    for claim in lisa_claims:
        rows.append({"record_type": "claim", **claim})

    lisa_rx = [
        {"rx_claim_id": "RX-LISA-01", "member_id": LISA_MEMBER_ID, "drug_name": "Trelegy Ellipta", "ndc": "00173088910", "days_supply": "30", "fill_date": "2026-02-01", "paid_amount": "640.00", "adherence_flag": "gap_risk", "provider_id": "PRV-RX-01"},
        {"rx_claim_id": "RX-LISA-02", "member_id": LISA_MEMBER_ID, "drug_name": "Albuterol HFA", "ndc": "00993067168", "days_supply": "30", "fill_date": "2026-02-05", "paid_amount": "48.00", "adherence_flag": "adherent", "provider_id": "PRV-RX-01"},
        {"rx_claim_id": "RX-LISA-03", "member_id": LISA_MEMBER_ID, "drug_name": "Prednisone 20mg", "ndc": "00555059802", "days_supply": "10", "fill_date": "2026-01-19", "paid_amount": "12.00", "adherence_flag": "burst", "provider_id": "PRV-RX-01"},
        {"rx_claim_id": "RX-LISA-04", "member_id": LISA_MEMBER_ID, "drug_name": "Azithromycin", "ndc": "00185012460", "days_supply": "5", "fill_date": "2026-01-19", "paid_amount": "18.50", "adherence_flag": "burst", "provider_id": "PRV-RX-01"},
        {"rx_claim_id": "RX-LISA-05", "member_id": LISA_MEMBER_ID, "drug_name": "Sertraline 50mg", "ndc": "00093030501", "days_supply": "30", "fill_date": "2026-02-08", "paid_amount": "22.00", "adherence_flag": "adherent", "provider_id": "PRV-RX-01"},
    ]
    for rx in lisa_rx:
        rows.append({"record_type": "medication", **rx})

    rows.append(
        {
            "record_type": "care_plan",
            "care_plan_id": "CP-LISA-COPD-01",
            "member_id": LISA_MEMBER_ID,
            "care_manager_id": "CM-01",
            "plan_name": "COPD Exacerbation Prevention Pathway",
            "status": "active",
            "start_date": "2026-01-25",
            "goals": "Reduce ER visits; close Trelegy gap; complete pulmonary rehab; arrange transport",
            "interventions": "Weekly CM outreach; inhaler teach-back; oxygen adherence check; SDOH transport voucher",
            "priority": "critical",
        }
    )
    rows.append(
        {
            "record_type": "sdoh",
            "sdoh_id": "SDOH-LISA-01",
            "member_id": LISA_MEMBER_ID,
            "transportation_barrier": "true",
            "food_insecurity": "false",
            "housing_instability": "false",
            "social_isolation": "moderate",
            "notes": "Missed two pulmonology follow-ups due to winter transit gaps; CM arranging medical ride benefit.",
        }
    )
    rows.append(
        {
            "record_type": "cost_driver",
            "cost_driver_id": "CD-LISA-01",
            "member_id": LISA_MEMBER_ID,
            "driver_category": "Avoidable ER",
            "annualized_impact": "8735.00",
            "recommendation": "Stand up 24/7 dyspnea triage line and same-day pulmonology slot",
            "priority": "P1",
        }
    )
    rows.append(
        {
            "record_type": "cost_driver",
            "cost_driver_id": "CD-LISA-02",
            "member_id": LISA_MEMBER_ID,
            "driver_category": "Medication Gap",
            "annualized_impact": "6400.00",
            "recommendation": "Auto-refill Trelegy + pharmacist outreach within 48h of gap",
            "priority": "P1",
        }
    )
    rows.append(
        {
            "record_type": "cost_driver",
            "cost_driver_id": "CD-LISA-03",
            "member_id": LISA_MEMBER_ID,
            "driver_category": "Readmission Risk",
            "annualized_impact": "15200.00",
            "recommendation": "Extend home health + RT visit within 72h of discharge",
            "priority": "P1",
        }
    )
    rows.append(
        {
            "record_type": "care_event",
            "care_event_id": "EVT-LISA-01",
            "member_id": LISA_MEMBER_ID,
            "event_type": "COPD exacerbation",
            "event_date": "2026-01-18",
            "setting": "Inpatient",
            "outcome": "Stabilized; discharged with home O2 and CM enrollment",
        }
    )
    rows.append(
        {
            "record_type": "care_event",
            "care_event_id": "EVT-LISA-02",
            "member_id": LISA_MEMBER_ID,
            "event_type": "Care manager outreach",
            "event_date": "2026-02-22",
            "setting": "Telephonic",
            "outcome": "Confirmed inhaler teach-back; scheduled pulmonary rehab assessment",
        }
    )

    # Remaining members (519 more → 520 total including Lisa)
    claim_counter = 1
    rx_counter = 1
    dx_counter = 1
    for i in range(1, MEMBER_COUNT):
        mid = f"MEM-{i:04d}"
        cond_name, icd = _pick(rng, conditions)
        plan = _pick(rng, plans)
        risk = _pick(rng, risk_tiers)
        if cond_name in ("COPD", "CHF") and rng.random() < 0.35:
            risk = "high"
        ytd_med = round(rng.uniform(800, 28000) if risk != "high" else rng.uniform(18000, 52000), 2)
        ytd_rx = round(rng.uniform(120, 4500) if risk != "high" else rng.uniform(2000, 8000), 2)
        er_visits = rng.randint(0, 1) if risk == "low" else rng.randint(1, 5)
        ip_admits = 0 if risk == "low" else rng.randint(0, 3)
        cm = _pick(rng, care_managers)
        pcp = _pick(rng, [p for p in providers if p["specialty"] in ("Primary Care", "Internal Medicine")] or providers)
        specialist_map = {
            "COPD": "PRV-PULM-01",
            "CHF": "PRV-CARD-01",
            "Diabetes": "PRV-ENDO-01",
            "CKD": "PRV-NEPH-01",
        }
        rows.append(
            {
                "record_type": "member",
                "member_id": mid,
                "member_name": f"{_pick(rng, first_names)} {_pick(rng, last_names)}",
                "dob": f"{rng.randint(1946, 1988)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
                "age": str(rng.randint(55, 79)),
                "gender": _pick(rng, ["F", "M"]),
                "state": _pick(rng, states),
                "county": _pick(rng, ["Hennepin", "Ramsey", "Dakota", "Anoka", "Washington"]),
                "plan_id": plan["plan_id"],
                "risk_tier": risk,
                "primary_condition": cond_name,
                "icd10": icd,
                "secondary_conditions": _pick(rng, ["Hypertension", "Depression", "Obesity", "CKD", "none"]),
                "eligibility_status": _pick(rng, ["Eligible", "Eligible", "Eligible", "Pending"]),
                "enrollment_status": _pick(rng, ["Active", "Active", "Active", "Terminated"]),
                "ytd_medical_cost": f"{ytd_med:.2f}",
                "ytd_rx_cost": f"{ytd_rx:.2f}",
                "ytd_total_cost": f"{(ytd_med + ytd_rx):.2f}",
                "pmpm_cost": f"{((ytd_med + ytd_rx) / 12):.2f}",
                "er_visits_12m": str(er_visits),
                "inpatient_admits_12m": str(ip_admits),
                "readmission_flag": "true" if ip_admits >= 2 and rng.random() < 0.4 else "false",
                "care_manager_id": cm["care_manager_id"] if risk in ("high", "rising_risk") else "",
                "pcp_provider_id": pcp["provider_id"],
                "specialist_provider_id": specialist_map.get(cond_name, "PRV-PCP-01"),
                "case_narrative": f"{cond_name} member on {plan['plan_name']} with {risk} risk and {er_visits} ER visits.",
                "agent_focus": "cost_of_care|population_health",
            }
        )

        rows.append(
            {
                "record_type": "diagnosis",
                "diagnosis_id": f"DX-{dx_counter:05d}",
                "member_id": mid,
                "icd10": icd,
                "diagnosis_name": cond_name,
                "onset_date": f"20{rng.randint(18,25)}-{rng.randint(1,12):02d}-01",
                "status": "active",
                "severity": "primary",
            }
        )
        dx_counter += 1

        n_claims = 1 if risk == "low" else rng.randint(2, 4)
        for _ in range(n_claims):
            claim_type = _pick(rng, ["PCP", "ER", "Inpatient", "Specialist", "Pharmacy"])
            allowed = round(rng.uniform(120, 22000) if claim_type == "Inpatient" else rng.uniform(80, 3200), 2)
            paid = round(allowed * rng.uniform(0.7, 0.95), 2)
            rows.append(
                {
                    "record_type": "claim",
                    "claim_id": f"CLM-{claim_counter:06d}",
                    "member_id": mid,
                    "plan_id": plan["plan_id"],
                    "provider_id": _pick(rng, providers)["provider_id"],
                    "service_date": f"2025-{rng.randint(5,12):02d}-{rng.randint(1,28):02d}",
                    "claim_type": claim_type,
                    "procedure_code": _pick(rng, ["99214", "99285", "99223", "99215", "G0299"]),
                    "diagnosis_code": icd,
                    "allowed_amount": f"{allowed:.2f}",
                    "paid_amount": f"{paid:.2f}",
                    "claim_status": _pick(rng, ["paid", "paid", "paid", "pending", "denied"]),
                    "cost_driver": _pick(rng, ["Routine care", "Avoidable ER", "Medication", "Specialty follow-up", "Admission"]),
                }
            )
            claim_counter += 1

        if rng.random() < 0.7:
            rows.append(
                {
                    "record_type": "medication",
                    "rx_claim_id": f"RX-{rx_counter:06d}",
                    "member_id": mid,
                    "drug_name": _pick(rng, ["Metformin", "Lisinopril", "Atorvastatin", "Albuterol HFA", "Insulin", "Sertraline", "Trelegy Ellipta", "Furosemide"]),
                    "ndc": f"000{rng.randint(10000,99999)}01",
                    "days_supply": _pick(rng, ["30", "90"]),
                    "fill_date": f"2026-0{rng.randint(1,3)}-{rng.randint(1,28):02d}",
                    "paid_amount": f"{rng.uniform(15, 700):.2f}",
                    "adherence_flag": _pick(rng, ["adherent", "adherent", "gap_risk"]),
                    "provider_id": "PRV-RX-01",
                }
            )
            rx_counter += 1

        if risk in ("high", "rising_risk") and rng.random() < 0.55:
            rows.append(
                {
                    "record_type": "care_plan",
                    "care_plan_id": f"CP-{mid}",
                    "member_id": mid,
                    "care_manager_id": cm["care_manager_id"],
                    "plan_name": f"{cond_name} Cost Containment Plan",
                    "status": "active",
                    "start_date": "2026-01-15",
                    "goals": f"Reduce avoidable utilization for {cond_name}",
                    "interventions": "CM outreach; medication reconciliation; specialist follow-up",
                    "priority": "high" if risk == "high" else "medium",
                }
            )
            rows.append(
                {
                    "record_type": "cost_driver",
                    "cost_driver_id": f"CD-{mid}",
                    "member_id": mid,
                    "driver_category": _pick(rng, ["Avoidable ER", "Medication Gap", "Readmission Risk", "Specialty Leakage"]),
                    "annualized_impact": f"{rng.uniform(1200, 18000):.2f}",
                    "recommendation": "Engage care manager and close clinical gaps",
                    "priority": _pick(rng, ["P1", "P2", "P3"]),
                }
            )
            if rng.random() < 0.4:
                rows.append(
                    {
                        "record_type": "sdoh",
                        "sdoh_id": f"SDOH-{mid}",
                        "member_id": mid,
                        "transportation_barrier": _pick(rng, ["true", "false"]),
                        "food_insecurity": _pick(rng, ["true", "false", "false"]),
                        "housing_instability": _pick(rng, ["true", "false", "false"]),
                        "social_isolation": _pick(rng, ["low", "moderate", "high"]),
                        "notes": "SDOH screen captured during CM intake.",
                    }
                )

    # Schema profile for ontology discovery + structured graph
    tables = [
        {
            "name": "members",
            "columns": [
                {"name": "member_id", "type": "string"},
                {"name": "member_name", "type": "string"},
                {"name": "plan_id", "type": "string"},
                {"name": "primary_condition", "type": "string"},
                {"name": "icd10", "type": "string"},
                {"name": "risk_tier", "type": "string"},
                {"name": "ytd_total_cost", "type": "number"},
                {"name": "care_manager_id", "type": "string"},
                {"name": "pcp_provider_id", "type": "string"},
                {"name": "specialist_provider_id", "type": "string"},
            ],
            "primary_key": ["member_id"],
        },
        {
            "name": "plans",
            "columns": [
                {"name": "plan_id", "type": "string"},
                {"name": "plan_name", "type": "string"},
                {"name": "coverage_type", "type": "string"},
                {"name": "network_id", "type": "string"},
                {"name": "pmpm", "type": "number"},
            ],
            "primary_key": ["plan_id"],
        },
        {
            "name": "providers",
            "columns": [
                {"name": "provider_id", "type": "string"},
                {"name": "provider_name", "type": "string"},
                {"name": "specialty", "type": "string"},
                {"name": "network_id", "type": "string"},
                {"name": "npi", "type": "string"},
            ],
            "primary_key": ["provider_id"],
        },
        {
            "name": "claims",
            "columns": [
                {"name": "claim_id", "type": "string"},
                {"name": "member_id", "type": "string"},
                {"name": "plan_id", "type": "string"},
                {"name": "provider_id", "type": "string"},
                {"name": "claim_type", "type": "string"},
                {"name": "diagnosis_code", "type": "string"},
                {"name": "allowed_amount", "type": "number"},
                {"name": "paid_amount", "type": "number"},
                {"name": "cost_driver", "type": "string"},
            ],
            "primary_key": ["claim_id"],
        },
        {
            "name": "diagnoses",
            "columns": [
                {"name": "diagnosis_id", "type": "string"},
                {"name": "member_id", "type": "string"},
                {"name": "icd10", "type": "string"},
                {"name": "diagnosis_name", "type": "string"},
                {"name": "severity", "type": "string"},
            ],
            "primary_key": ["diagnosis_id"],
        },
        {
            "name": "medications",
            "columns": [
                {"name": "rx_claim_id", "type": "string"},
                {"name": "member_id", "type": "string"},
                {"name": "drug_name", "type": "string"},
                {"name": "paid_amount", "type": "number"},
                {"name": "adherence_flag", "type": "string"},
                {"name": "provider_id", "type": "string"},
            ],
            "primary_key": ["rx_claim_id"],
        },
        {
            "name": "care_plans",
            "columns": [
                {"name": "care_plan_id", "type": "string"},
                {"name": "member_id", "type": "string"},
                {"name": "care_manager_id", "type": "string"},
                {"name": "plan_name", "type": "string"},
                {"name": "priority", "type": "string"},
            ],
            "primary_key": ["care_plan_id"],
        },
        {
            "name": "care_managers",
            "columns": [
                {"name": "care_manager_id", "type": "string"},
                {"name": "care_manager_name", "type": "string"},
                {"name": "panel", "type": "string"},
            ],
            "primary_key": ["care_manager_id"],
        },
        {
            "name": "cost_drivers",
            "columns": [
                {"name": "cost_driver_id", "type": "string"},
                {"name": "member_id", "type": "string"},
                {"name": "driver_category", "type": "string"},
                {"name": "annualized_impact", "type": "number"},
                {"name": "recommendation", "type": "string"},
            ],
            "primary_key": ["cost_driver_id"],
        },
        {
            "name": "sdoh",
            "columns": [
                {"name": "sdoh_id", "type": "string"},
                {"name": "member_id", "type": "string"},
                {"name": "transportation_barrier", "type": "string"},
                {"name": "food_insecurity", "type": "string"},
                {"name": "housing_instability", "type": "string"},
            ],
            "primary_key": ["sdoh_id"],
        },
        {
            "name": "care_events",
            "columns": [
                {"name": "care_event_id", "type": "string"},
                {"name": "member_id", "type": "string"},
                {"name": "event_type", "type": "string"},
                {"name": "event_date", "type": "string"},
                {"name": "setting", "type": "string"},
            ],
            "primary_key": ["care_event_id"],
        },
    ]

    type_counts: Dict[str, int] = {}
    for row in rows:
        rt = str(row.get("record_type") or "unknown")
        type_counts[rt] = type_counts.get(rt, 0) + 1

    connection_info: Dict[str, Any] = {
        "type": "synthetic_cost_of_care",
        "database_profile": "cost_of_care_agents",
        "domains": list(type_counts.keys()),
        "rows_imported": len(rows),
        "member_count": MEMBER_COUNT,
        "hero_member_id": LISA_MEMBER_ID,
        "hero_member_name": LISA_NAME,
        "hero_condition": "COPD",
        "tables": tables,
        "schema_tables": tables,
        "collections": [t["name"] for t in tables],
        "per_collection": [
            {
                "name": t["name"],
                "documents_imported": type_counts.get(t["name"].rstrip("s"), type_counts.get(t["name"][:-1] if t["name"].endswith("s") else t["name"], 0)),
                "columns": [c["name"] if isinstance(c, dict) else str(c) for c in t["columns"]],
            }
            for t in tables
        ],
        "columns": sorted({c["name"] for t in tables for c in t["columns"]}),
        "record_type_counts": type_counts,
        "sample_rows": [r for r in rows if r.get("member_id") == LISA_MEMBER_ID][:8],
    }

    # Fix per_collection counts using actual record_type names
    singular_map = {
        "members": "member",
        "plans": "plan",
        "providers": "provider",
        "claims": "claim",
        "diagnoses": "diagnosis",
        "medications": "medication",
        "care_plans": "care_plan",
        "care_managers": "care_manager",
        "cost_drivers": "cost_driver",
        "sdoh": "sdoh",
        "care_events": "care_event",
    }
    for entry in connection_info["per_collection"]:
        rt = singular_map.get(entry["name"], entry["name"])
        entry["documents_imported"] = type_counts.get(rt, 0)

    return rows, connection_info
