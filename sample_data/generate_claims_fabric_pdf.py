#!/usr/bin/env python3
"""Generate a rich claims-domain PDF for Weave Knowledge Fabric upload."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

OUTPUT = Path(__file__).resolve().parent / "Weave_Claims_Knowledge_Fabric_Guide.pdf"


class ClaimsGuidePDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(90, 100, 120)
        self.cell(0, 8, "Weave Claims Knowledge Fabric | Tata Consultancy Services", align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}/{{nb}}", align="C")

    def cover(self):
        self.add_page()
        self.set_fill_color(15, 23, 42)
        self.rect(0, 0, 210, 297, style="F")
        self.set_y(55)
        self.set_font("Helvetica", "B", 28)
        self.set_text_color(255, 255, 255)
        self.multi_cell(0, 14, "Healthcare Claims\nKnowledge Fabric", align="C")
        self.ln(8)
        self.set_font("Helvetica", "", 14)
        self.set_text_color(148, 163, 184)
        self.multi_cell(
            0,
            8,
            "Enterprise adjudication, duplicate detection, and payer operations\n"
            "Reference guide for Weave fabric creation",
            align="C",
        )
        self.ln(20)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(94, 200, 242)
        self.cell(0, 8, "TCS Weave Platform", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(180, 190, 210)
        self.cell(0, 8, datetime.now().strftime("%B %Y"), align="C")

    def section(self, title: str):
        self.set_x(self.l_margin)
        self.ln(4)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(30, 41, 59)
        self.multi_cell(0, 8, title)
        self.set_draw_color(94, 200, 242)
        self.set_line_width(0.6)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def body(self, text: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 41, 59)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def bullet(self, text: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 41, 59)
        self.multi_cell(0, 5.5, f"  -  {text}")

    def table_header(self, cols: list[tuple[str, int]]):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(241, 245, 249)
        self.set_text_color(30, 41, 59)
        for label, width in cols:
            self.cell(width, 7, label, border=1, fill=True)
        self.ln()

    def table_row(self, cols: list[tuple[str, int]]):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(51, 65, 85)
        for label, width in cols:
            self.cell(width, 6, label[:48], border=1)
        self.ln()


def build() -> Path:
    pdf = ClaimsGuidePDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.cover()

    pdf.add_page()
    pdf.section("1. Executive Summary")
    pdf.body(
        "This document defines the healthcare claims domain model used by Tata Consultancy Services "
        "Weave Knowledge Fabric for payer and health-plan operations. It covers professional and "
        "institutional claims, adjudication lifecycle, duplicate detection, financial fields, "
        "governance, and agent-ready query patterns. Upload this PDF to create your first Claims "
        "Knowledge Fabric and ask natural-language questions about adjudication, duplicates, "
        "denials, and member-provider relationships."
    )

    pdf.section("2. Claim Types and Lines of Business")
    pdf.bullet("Professional Claims (CMS-1500): physician, lab, outpatient services billed on a per-visit or per-line basis.")
    pdf.bullet("Institutional Claims (UB-04): hospital inpatient/outpatient, facility fees, revenue codes.")
    pdf.bullet("Commercial: employer-sponsored and individual market plans with negotiated allowed amounts.")
    pdf.bullet("Medicare Advantage (MA): Medicare benefits delivered through private carriers; CMS risk adjustment applies.")
    pdf.bullet("Medicaid: state-federal program with stricter eligibility and prior authorization rules.")
    pdf.ln(2)
    pdf.body(
        "Each claim line carries claim_type, line_of_business, place_of_service, bill_type (institutional), "
        "and revenue_code where applicable. Agents use these dimensions to route edits and apply "
        "line-of-business-specific policies."
    )

    pdf.section("3. End-to-End Claims Lifecycle")
    pdf.body(
        "Stage 1 - Intake: Claims arrive from CAS, EDI Gateway, Clearinghouse, or Provider Portal. "
        "received_date is when the payer accepts the submission; date_of_service is when care was rendered.\n\n"
        "Stage 2 - Validation: Eligibility, provider credentialing (NPI/TIN), authorization, and coding edits run. "
        "edit_path may be None, Coding Edit, Pricing Edit, Eligibility Edit, or Multiple Edits.\n\n"
        "Stage 3 - Adjudication: Rules engine and optional LLM reasoner compute allowed_amount, paid_amount, "
        "and patient_responsibility_amount. adjudication_status includes Pending, In Review, Completed.\n\n"
        "Stage 4 - Payment or Denial: denial_reason_code populated on denial. payer_claim_control_number (PCCN) "
        "tracks payer-side identity.\n\n"
        "Stage 5 - Audit and Feedback: audit_id, audit_timestamp, governance_status, and feedback_label support "
        "model governance and human-in-the-loop review."
    )

    pdf.section("4. Core Data Model (Claim Header and Line)")
    cols = [("Field", 45), ("Description", 145)]
    pdf.table_header(cols)
    rows = [
        ("claim_id", "Unique claim identifier e.g. CLM100001"),
        ("claim_line_id", "Line-level key e.g. CLM100001-01"),
        ("member_id", "Subscriber/beneficiary identifier"),
        ("provider_npi", "National Provider Identifier (10 digits)"),
        ("provider_tin", "Tax identification for billing entity"),
        ("payer_claim_control_number", "Payer internal control number (PCCN)"),
        ("date_of_service", "Date care was provided"),
        ("received_date", "Date claim entered payer workflow"),
        ("procedure_code", "CPT/HCPCS e.g. 99214, 93000, G0439"),
        ("diagnosis_code", "ICD-10-CM e.g. I10, E11.9, Z00.00"),
        ("modifier", "Procedure modifier e.g. 25, 59, GT, 95"),
        ("billed_amount", "Amount charged by provider"),
        ("allowed_amount", "Contracted or policy-allowed amount"),
        ("paid_amount", "Amount paid by plan after edits"),
        ("patient_responsibility_amount", "Member owes: copay, coinsurance, deductible"),
    ]
    for field, desc in rows:
        pdf.table_row([(field, 45), (desc, 145)])

    pdf.ln(4)
    pdf.section("5. Duplicate Claim Detection")
    pdf.body(
        "Duplicate detection protects payers from paying the same service twice. Weave supports "
        "agentic duplicate analysis combining rules and LLM reasoning (llm_reasoning_used = Y/N).\n\n"
        "duplicate_match_type values: Exact Duplicate, Probable Duplicate, Related Resubmission, Not Duplicate.\n\n"
        "duplicate_risk_score ranges from 0.0 (low) to 1.0 (high). Scores above 0.85 typically require human review.\n\n"
        "Similarity dimensions: similarity_member, similarity_provider, similarity_dos (date of service), "
        "similarity_procedure, similarity_amount. Each is a normalized score 0-1.\n\n"
        "duplicate_candidate_group_id groups related claims for batch review. prior_matching_claim_id links "
        "to a previously adjudicated claim when a resubmission or correction is detected.\n\n"
        "decision_route options: Auto Deny Duplicate, Proceed Adjudication, Route to Human Review, Pend for Investigation."
    )

    pdf.section("6. Detailed Scenario - CLM100001 (Not Duplicate)")
    pdf.body(
        "Claim CLM100001 line CLM100001-01 is a Professional Medicaid claim from source_system CAS. "
        "Member MBR000370 received service on 2026-02-11; claim received 2026-02-18. Provider Group 40 "
        "(NPI 3119634399) billed procedure G0439 with modifier 95 and diagnosis K21.9 (GERD). "
        "Billed $182.34, allowed $104.12, paid $94.68, patient responsibility $87.66. "
        "Duplicate group DG100001 assigned; duplicate_risk_score 0.103 indicates low risk. "
        "Rules triggered: 0. LLM reasoning used: Yes. reasoning_summary: No strong duplicate indicators found. "
        "decision_route: Proceed Adjudication. adjudication_status: In Review. sensitivity_level: Restricted."
    )

    pdf.section("7. Detailed Scenario - Probable Duplicate Pattern")
    pdf.body(
        "A probable duplicate often shows: same member_id, same provider_npi, same date_of_service, "
        "same procedure_code, and billed_amount within 5% of a prior claim within 90 days. "
        "Example pattern: Member MBR000155 has claim CLM100002 for institutional service 93000 on "
        "2026-01-28 with billed $476.80. If a second claim arrives with identical DOS, member, provider, "
        "and procedure, similarity scores exceed 0.75 and duplicate_risk_score rises above 0.70. "
        "rules_triggered increases; rule_hit_count may be 2 or more. human_review_required = Y. "
        "analyst_action may be set to Confirm Duplicate, Release for Payment, or Request Medical Records."
    )

    pdf.section("8. Diagnosis and Procedure Reference")
    pdf.table_header([("Code", 25), ("Type", 30), ("Clinical Meaning", 135)])
    ref = [
        ("I10", "ICD-10", "Essential (primary) hypertension"),
        ("E11.9", "ICD-10", "Type 2 diabetes mellitus without complications"),
        ("Z00.00", "ICD-10", "General adult medical examination"),
        ("K21.9", "ICD-10", "Gastro-esophageal reflux disease without esophagitis"),
        ("M25.561", "ICD-10", "Pain in right knee"),
        ("R10.9", "ICD-10", "Unspecified abdominal pain"),
        ("99213", "CPT", "Office visit, established patient, low complexity"),
        ("99214", "CPT", "Office visit, established patient, moderate complexity"),
        ("93000", "CPT", "Electrocardiogram, complete"),
        ("80053", "CPT", "Comprehensive metabolic panel"),
        ("G0439", "HCPCS", "Annual wellness visit, subsequent"),
        ("71046", "CPT", "Chest X-ray, two views"),
    ]
    for code, typ, meaning in ref:
        pdf.table_row([(code, 25), (typ, 30), (meaning, 135)])

    pdf.section("9. Financial Adjudication Rules")
    pdf.body(
        "allowed_amount is typically the lesser of billed_amount and fee schedule or contract rate. "
        "paid_amount = allowed_amount minus patient_responsibility_amount minus plan withholds. "
        "patient_responsibility_amount includes copay, coinsurance, and deductible applied to the line. "
        "estimated_adjudication_cost_saved_usd quantifies automation savings when auto-adjudication avoids manual review. "
        "estimated_cycle_time_saved_hours measures operational efficiency gains from straight-through processing."
    )

    pdf.section("10. Governance, Audit, and Sensitivity")
    pdf.bullet("sensitivity_level: Public, Internal, Confidential, Restricted, PHI.")
    pdf.bullet("governance_policy_applied: e.g. dup_policy_v3 for duplicate governance.")
    pdf.bullet("governance_status: Logged, Approved, Reviewed, Escalated.")
    pdf.bullet("model_version: rules_v1, hybrid_v2, llm_reasoner_v1 indicate which engine adjudicated.")
    pdf.bullet("confidence_band: Low, Medium, High for automated decisions.")
    pdf.bullet("explanation_version: exp_v2 tracks explainability schema for regulators.")
    pdf.ln(2)

    pdf.section("11. Source Systems and Integration")
    pdf.body(
        "source_system identifies claim origin: CAS (core admin system), EDI Gateway (X12 837), "
        "Clearinghouse (intermediary), Provider Portal (direct submission). "
        "claim_frequency_code 1 = original claim; 7 = replacement; 8 = void. "
        "corrected_claim_indicator Y/N flags resubmissions tied to original_claim_reference. "
        "in_flight_claim_indicator Y means claim is actively in workflow and should not be reprocessed."
    )

    pdf.section("12. Agent Query Examples for Weave Fabric")
    pdf.bullet("What is the adjudication workflow for a professional Medicaid claim?")
    pdf.bullet("How is duplicate_risk_score calculated and when is human review required?")
    pdf.bullet("Explain the difference between billed, allowed, and paid amounts on claim line CLM100001.")
    pdf.bullet("Which ICD-10 code represents Type 2 diabetes and which CPT is an office visit?")
    pdf.bullet("What decision_route applies when duplicate_match_type is Probable Duplicate?")
    pdf.bullet("List governance fields required for audit of LLM-assisted duplicate decisions.")
    pdf.bullet("What place_of_service codes apply to inpatient hospital vs physician office?")
    pdf.ln(2)

    pdf.section("13. Place of Service Quick Reference")
    pdf.table_header([("POS", 20), ("Setting", 60), ("Typical Claim Type", 110)])
    pos_rows = [
        ("11", "Office", "Professional"),
        ("22", "Outpatient Hospital", "Institutional or Professional"),
        ("23", "Emergency Room", "Professional"),
        ("31", "Skilled Nursing Facility", "Institutional"),
        ("49", "Independent Clinic", "Professional"),
    ]
    for pos, setting, ctype in pos_rows:
        pdf.table_row([(pos, 20), (setting, 60), (ctype, 110)])

    pdf.section("14. Denial and Edit Paths")
    pdf.body(
        "Common denial_reason_code categories: CO (contractual obligation), PR (patient responsibility), "
        "OA (other adjustment). Coding Edit triggers when diagnosis does not support procedure or modifier is invalid. "
        "Pricing Edit applies when charge exceeds fee schedule. Eligibility Edit fires when member not eligible on DOS. "
        "Multiple Edits indicates sequential or parallel edits before final disposition."
    )

    pdf.section("15. Sample Claim Batch Summary")
    pdf.body(
        "A typical Weave claims fabric batch contains 2,000 claim lines spanning Commercial, Medicare Advantage, "
        "and Medicaid. Approximately 12% enter duplicate_candidate_group review. Auto-adjudication rate targets "
        "78% straight-through processing. LLM reasoning augments rules when similarity scores fall in the gray zone "
        "between 0.45 and 0.85. Average processing_time_ms for automated path is 800-2000 ms per line. "
        "Human review queue prioritizes Restricted and Confidential sensitivity levels and high duplicate_risk_score."
    )

    pdf.output(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    path = build()
    print(f"Created: {path}")
