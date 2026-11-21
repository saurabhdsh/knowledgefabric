"""Cost-of-Care / CSNP healthcare domain pack."""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

from app.services.domain_packs.base import DomainPack


def _add(
    out: List[Dict[str, Any]],
    name: str,
    cols: Sequence[str],
    relevant: List[str],
    rows_imported: int,
) -> None:
    out.append({
        "name": name,
        "documents_imported": int(rows_imported or 0),
        "columns": relevant[:40] or list(cols)[:40],
    })


class HealthcareCostOfCarePack(DomainPack):
    def __init__(self) -> None:
        super().__init__(
            id="healthcare_cost_of_care",
            label="Healthcare — Cost of Care / CSNP",
            detect_columns={
                "member_id", "member_name", "claim_id", "risk_tier",
                "primary_condition", "ytd_total_cost", "care_plan_id",
                "sdoh_id", "cost_driver_id",
            },
            collections={
                "members", "claims", "plans", "providers", "diagnoses",
                "medications", "care_plans", "care_managers", "cost_drivers",
                "sdoh", "care_events",
            },
            label_fields={
                "members": ["member_name", "member_id", "primary_condition", "risk_tier"],
                "claims": ["claim_id", "claim_type", "diagnosis_code", "paid_amount", "member_id"],
                "plans": ["plan_name", "plan_id", "coverage_type"],
                "providers": ["provider_name", "specialty", "provider_id", "npi"],
                "diagnoses": ["diagnosis_name", "icd10", "diagnosis_id", "member_id"],
                "medications": ["drug_name", "rx_claim_id", "adherence_flag", "member_id"],
                "care_plans": ["plan_name", "care_plan_id", "priority", "member_id"],
                "care_managers": ["care_manager_name", "panel", "care_manager_id"],
                "cost_drivers": ["driver_category", "cost_driver_id", "annualized_impact", "member_id"],
                "sdoh": ["sdoh_id", "member_id", "transportation_barrier"],
                "care_events": ["event_type", "care_event_id", "event_date", "member_id"],
            },
            id_hints={
                "members": ("member_id", "member_name"),
                "claims": ("claim_id",),
                "plans": ("plan_id", "plan_name"),
                "providers": ("provider_id", "provider_name"),
                "diagnoses": ("diagnosis_id", "icd10"),
                "medications": ("rx_claim_id", "drug_name"),
                "care_plans": ("care_plan_id",),
                "care_managers": ("care_manager_id", "care_manager_name"),
                "cost_drivers": ("cost_driver_id", "driver_category"),
                "sdoh": ("sdoh_id",),
                "care_events": ("care_event_id", "event_type"),
            },
            synonyms={
                "member": ["patient", "beneficiary", "enrollee"],
                "claim": ["encounter", "service_line"],
                "diagnosis": ["condition", "icd"],
            },
            sensitive_keywords={
                "member_id", "patient_id", "dob", "ssn", "member_name", "phone", "address",
            },
        )

    def business_rules(self) -> List[Dict[str, Any]]:
        """Cost-of-Care / CSNP operating rules for ontology constraints."""
        return [
            {
                "expression": "Every Claim.member_id MUST reference an enrolled Member.member_id",
                "confidence": 0.98,
                "related_entity": "claims",
                "constraint_type": "reference",
            },
            {
                "expression": "Member.plan_id MUST reference an active Plans.plan_id",
                "confidence": 0.96,
                "related_entity": "members",
                "constraint_type": "reference",
            },
            {
                "expression": "IF Claim.paid_amount IS NOT NULL THEN Claim.paid_amount <= Claim.allowed_amount",
                "confidence": 0.94,
                "related_entity": "claims",
                "constraint_type": "range",
            },
            {
                "expression": "Member.ytd_total_cost SHOULD approximate Member.ytd_medical_cost + Member.ytd_rx_cost (±5%)",
                "confidence": 0.9,
                "related_entity": "members",
                "constraint_type": "business_rule",
            },
            {
                "expression": "IF Member.risk_tier IN ('High','Very High') AND CostDrivers.driver_category = 'Avoidable ER' THEN Member MUST have an active CarePlans row",
                "confidence": 0.93,
                "related_entity": "care_plans",
                "constraint_type": "business_rule",
            },
            {
                "expression": "IF Medications.adherence_flag = false THEN CareManagers outreach MUST be scheduled within 7 days",
                "confidence": 0.91,
                "related_entity": "medications",
                "constraint_type": "business_rule",
            },
            {
                "expression": "CostDrivers with priority = 'P1' REQUIRE Member.care_manager_id IS NOT NULL",
                "confidence": 0.95,
                "related_entity": "cost_drivers",
                "constraint_type": "business_rule",
            },
            {
                "expression": "IF Sdoh.transportation_barrier OR Sdoh.food_insecurity OR Sdoh.housing_instability THEN CarePlans.priority MUST be P1 or P2",
                "confidence": 0.88,
                "related_entity": "sdoh",
                "constraint_type": "business_rule",
            },
            {
                "expression": "CareEvents.event_type = 'ER' for High-risk Members SHOULD spawn or update a CostDrivers row with driver_category = 'Avoidable ER'",
                "confidence": 0.87,
                "related_entity": "care_events",
                "constraint_type": "business_rule",
            },
            {
                "expression": "Member.member_id, Claim.claim_id, Plans.plan_id, Providers.provider_id are UNIQUE identifiers",
                "confidence": 0.99,
                "related_entity": "members",
                "constraint_type": "unique",
            },
            {
                "expression": "Diagnoses.icd10 MUST be a valid ICD-10-CM code pattern when present",
                "confidence": 0.86,
                "related_entity": "diagnoses",
                "constraint_type": "pattern",
            },
            {
                "expression": "IF Member.eligibility_status != 'Active' THEN new Claims SHOULD NOT be payable",
                "confidence": 0.92,
                "related_entity": "claims",
                "constraint_type": "business_rule",
            },
        ]

    def infer_collections(
        self,
        columns: Sequence[str],
        *,
        rows_imported: int = 0,
    ) -> List[Dict[str, Any]]:
        cols = [str(c) for c in columns if str(c).strip()]
        lower = {c.lower() for c in cols}
        out: List[Dict[str, Any]] = []

        if {"member_id", "member_name"} & lower or (
            "member_id" in lower and {"risk_tier", "ytd_total_cost", "primary_condition"} & lower
        ):
            _add(out, "members", cols, [c for c in cols if c.lower().startswith("member") or c.lower() in {
                "dob", "age", "gender", "state", "county", "plan_id", "risk_tier",
                "primary_condition", "icd10", "eligibility_status", "enrollment_status",
                "ytd_medical_cost", "ytd_rx_cost", "ytd_total_cost", "pmpm_cost",
                "er_visits_12m", "inpatient_admits_12m", "care_manager_id",
                "pcp_provider_id", "specialist_provider_id", "case_narrative", "agent_focus",
            }], rows_imported)
        if {"claim_id"} & lower or (
            {"allowed_amount", "paid_amount"} & lower and any("claim" in c for c in lower)
        ):
            _add(out, "claims", cols, [c for c in cols if "claim" in c.lower() or c.lower() in {
                "member_id", "plan_id", "provider_id", "service_date", "claim_type",
                "procedure_code", "diagnosis_code", "allowed_amount", "paid_amount",
                "claim_status", "cost_driver",
            }], rows_imported)
        if {"plan_id", "plan_name", "coverage_type"} & lower:
            _add(out, "plans", cols, [c for c in cols if "plan" in c.lower() or c.lower() in {
                "coverage_type", "network_id", "pmpm",
            }], rows_imported)
        if {"provider_id", "provider_name", "npi", "specialty"} & lower:
            _add(out, "providers", cols, [c for c in cols if "provider" in c.lower() or c.lower() in {
                "npi", "specialty", "network_id",
            }], rows_imported)
        if {"diagnosis_id", "icd10", "diagnosis_name"} & lower:
            _add(out, "diagnoses", cols, [c for c in cols if "diagnos" in c.lower() or c.lower() in {
                "member_id", "icd10", "onset_date", "severity",
            }], rows_imported)
        if {"rx_claim_id", "drug_name", "adherence_flag"} & lower:
            _add(out, "medications", cols, [c for c in cols if c.lower() in {
                "rx_claim_id", "member_id", "drug_name", "ndc", "days_supply", "fill_date",
                "paid_amount", "adherence_flag", "provider_id",
            } or "drug" in c.lower() or "rx" in c.lower()], rows_imported)
        if {"care_plan_id", "interventions", "goals"} & lower:
            _add(out, "care_plans", cols, [c for c in cols if "care_plan" in c.lower() or c.lower() in {
                "member_id", "care_manager_id", "plan_name", "status", "start_date", "goals",
                "interventions", "priority",
            }], rows_imported)
        if {"care_manager_id", "care_manager_name", "panel"} & lower:
            _add(out, "care_managers", cols, [c for c in cols if "care_manager" in c.lower() or c.lower() in {
                "panel", "phone",
            }], rows_imported)
        if {"cost_driver_id", "driver_category", "annualized_impact"} & lower:
            _add(out, "cost_drivers", cols, [c for c in cols if "cost_driver" in c.lower() or c.lower() in {
                "member_id", "driver_category", "annualized_impact", "recommendation", "priority",
            }], rows_imported)
        if {"sdoh_id", "transportation_barrier", "food_insecurity"} & lower:
            _add(out, "sdoh", cols, [c for c in cols if c.lower().startswith("sdoh") or c.lower() in {
                "member_id", "transportation_barrier", "food_insecurity", "housing_instability",
                "social_isolation", "notes",
            }], rows_imported)
        if {"care_event_id", "event_type", "event_date"} & lower:
            _add(out, "care_events", cols, [c for c in cols if "event" in c.lower() or c.lower() in {
                "member_id", "setting", "outcome",
            }], rows_imported)
        return out


healthcare_cost_of_care_pack = HealthcareCostOfCarePack()
