#!/usr/bin/env python3
"""Generate research knowledge fabric PDF for Weave Research-type fabric demos."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

OUTPUT = Path(__file__).resolve().parent / "Weave_Research_Knowledge_Fabric_Guide.pdf"


class ResearchGuidePDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(90, 100, 120)
        self.cell(
            0,
            8,
            "Weave Knowledge Fabric | Research Use Case | TCS",
            align="R",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}/{{nb}}", align="C")

    def cover(self):
        self.add_page()
        self.set_fill_color(11, 18, 32)
        self.rect(0, 0, 210, 297, style="F")
        self.set_fill_color(94, 200, 242)
        self.rect(0, 0, 210, 6, style="F")
        self.set_y(42)
        self.set_font("Helvetica", "B", 26)
        self.set_text_color(255, 255, 255)
        self.multi_cell(0, 13, "Research Knowledge Fabric\nEvidence Synthesis Guide", align="C")
        self.ln(6)
        self.set_font("Helvetica", "", 12)
        self.set_text_color(148, 163, 184)
        self.multi_cell(
            0,
            7,
            "Multi-study corpus for Research-type fabrics in Weave\n"
            "Methods, findings, limitations, and comparative evidence chains",
            align="C",
        )
        self.ln(12)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(94, 200, 242)
        self.cell(0, 8, "TCS Weave - Hybrid Retrieval Intelligence Platform", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(180, 190, 210)
        self.cell(0, 8, "Enterprise Research Demo | " + datetime.now().strftime("%B %Y"), align="C")
        self.ln(16)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(139, 156, 176)
        self.multi_cell(
            0,
            5,
            "Upload this document in Create Knowledge Fabric, select Research Knowledge Fabric, "
            "then use Test with LLM to ask complex multi-study synthesis questions.",
            align="C",
        )

    def section(self, title: str):
        self.set_x(self.l_margin)
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(15, 23, 42)
        self.multi_cell(0, 7, title)
        self.set_draw_color(94, 200, 242)
        self.set_line_width(0.5)
        y = self.get_y()
        self.line(self.l_margin, y, 210 - self.r_margin, y)
        self.ln(4)

    def body(self, text: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 41, 59)
        self.multi_cell(0, 5.5, text)
        self.ln(1.5)

    def bullet(self, text: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 41, 59)
        self.multi_cell(0, 5.5, f"- {text}")

    def subhead(self, title: str):
        self.set_x(self.l_margin)
        self.ln(1)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(51, 65, 85)
        self.multi_cell(0, 6, title)
        self.ln(1)


def build() -> Path:
    pdf = ResearchGuidePDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(16, 18, 16)

    pdf.cover()

    pdf.add_page()
    pdf.section("1. Purpose of this Research Corpus")
    pdf.body(
        "This guide is a self-contained research knowledge corpus designed for Weave. "
        "It synthesizes three fictional but realistic clinical-research style studies on "
        "digital adherence coaching for chronic cardiometabolic care. Use it to create a "
        "Research Knowledge Fabric and test multi-hop questions such as: which study design "
        "is strongest, where findings conflict, and what limitations remain unresolved."
    )
    pdf.body(
        "Recommended Weave setting: Create Knowledge Fabric -> Research Knowledge Fabric -> "
        "Upload PDF Documents -> upload this file -> Analyze & create fabric."
    )
    pdf.subhead("Suggested complex Test-with-LLM questions")
    pdf.bullet("Compare primary endpoints and effect sizes across Study A, Study B, and Study C.")
    pdf.bullet("Which study provides the strongest causal evidence and why?")
    pdf.bullet("Where do the studies agree, and where do they conflict on adherence outcomes?")
    pdf.bullet("What limitations would block a policy recommendation based only on this corpus?")
    pdf.bullet("Propose two follow-up research questions grounded in gaps visible in these studies.")

    pdf.section("2. Domain Framing")
    pdf.body(
        "Research domain: Digital therapeutic coaching for type 2 diabetes and hypertension "
        "adherence. Population of interest: adults 40-75 years with at least one cardiometabolic "
        "diagnosis. Intervention class: app-mediated coaching plus clinician escalation pathways. "
        "Comparator class: usual care or educational pamphlet control."
    )
    pdf.body(
        "Evidence types in this fabric: randomized controlled trial (RCT), pragmatic cluster trial, "
        "and prospective observational cohort. Agents should distinguish hypothesis, measured "
        "result, and interpretation, and must not invent statistical significance beyond what is stated."
    )

    pdf.add_page()
    pdf.section("3. Study A - Adaptive Coaching RCT (ADHERE-1)")
    pdf.subhead("Design and methods")
    pdf.body(
        "ADHERE-1 was a multi-center randomized controlled trial (n=842) conducted across six "
        "ambulatory clinics. Adults aged 45-70 with type 2 diabetes (HbA1c 7.5%-10.0%) were "
        "randomized 1:1 to adaptive digital coaching versus usual care. Primary endpoint: "
        "change in medication possession ratio (MPR) at 26 weeks. Secondary endpoints: HbA1c "
        "change, systolic blood pressure, and patient-reported activation (PAM-13)."
    )
    pdf.body(
        "Randomization used permuted blocks stratified by clinic and baseline MPR (<0.80 vs >=0.80). "
        "Outcome assessors were blinded; participants were not. Missing primary endpoint data "
        "were handled with multiple imputation under a missing-at-random assumption. Sample size "
        "targeted 80% power to detect a 0.08 absolute MPR difference (two-sided alpha 0.05)."
    )
    pdf.subhead("Key findings")
    pdf.bullet("Primary: adaptive coaching improved mean MPR by +0.11 versus usual care (95% CI 0.07 to 0.15, p<0.001).")
    pdf.bullet("HbA1c decreased by -0.42% vs -0.11% (between-group difference -0.31%, 95% CI -0.48 to -0.14).")
    pdf.bullet("Systolic BP difference was -3.1 mmHg (95% CI -5.4 to -0.8).")
    pdf.bullet("Serious adverse events were similar (4.1% coaching vs 3.8% usual care).")
    pdf.subhead("Limitations")
    pdf.bullet("Open-label participant awareness may inflate self-reported activation.")
    pdf.bullet("Follow-up limited to 26 weeks; durability beyond one year unknown.")
    pdf.bullet("Sites were urban academic clinics; rural generalizability is uncertain.")

    pdf.section("4. Study B - Pragmatic Cluster Trial (CARE-PATH)")
    pdf.subhead("Design and methods")
    pdf.body(
        "CARE-PATH was a pragmatic cluster-randomized trial of 24 primary-care practices "
        "(n=1,206 patients). Practices were randomized to a lighter coaching model with "
        "weekly SMS nudges and nurse escalation, versus pamphlet-based education. Primary "
        "endpoint: proportion of patients with MPR >=0.80 at 12 months. The design prioritized "
        "external validity over tight protocol control."
    )
    pdf.subhead("Key findings")
    pdf.bullet("Primary: 61% vs 54% achieved MPR >=0.80 (risk difference +7 percentage points, 95% CI +1 to +13).")
    pdf.bullet("HbA1c change was not statistically significant (-0.12%, 95% CI -0.29 to +0.05).")
    pdf.bullet("Implementation fidelity varied widely; four intervention practices delivered <50% of planned coaching contacts.")
    pdf.subhead("Limitations")
    pdf.bullet("Cluster contamination possible where clinicians covered multiple practices.")
    pdf.bullet("Lower intervention intensity than ADHERE-1; effect sizes are smaller and more heterogeneous.")
    pdf.bullet("No blinded outcome adjudication for MPR derived from pharmacy claims.")

    pdf.add_page()
    pdf.section("5. Study C - Observational Cohort (CONNECT-OBS)")
    pdf.subhead("Design and methods")
    pdf.body(
        "CONNECT-OBS followed 3,410 commercially insured adults who opted into a vendor "
        "coaching app between 2022 and 2024. Exposure was defined as completing >=8 coaching "
        "sessions in 90 days. Outcomes were adherence and emergency department visits over "
        "18 months. Analyses used propensity-score overlap weighting for age, sex, comorbidity "
        "index, baseline MPR, and prior hospitalizations."
    )
    pdf.subhead("Key findings")
    pdf.bullet("Associated MPR improvement +0.09 (95% CI 0.06 to 0.12) among high-engagement users versus low-engagement users.")
    pdf.bullet("ED visits were 12% lower in the high-engagement group (IRR 0.88, 95% CI 0.79 to 0.98).")
    pdf.bullet("Users with low digital literacy showed attenuated adherence gains.")
    pdf.subhead("Limitations")
    pdf.bullet("Observational design; residual confounding cannot be excluded despite weighting.")
    pdf.bullet("Opt-in population likely healthier and more digitally confident than average clinic panels.")
    pdf.bullet("Session completion is a post-baseline behavior, raising immortal-time and healthy-user bias risks.")

    pdf.section("6. Comparative Synthesis")
    pdf.body(
        "Across the corpus, digital coaching is consistently associated with better medication "
        "adherence. The strongest causal claim comes from ADHERE-1 (individual RCT, clear "
        "primary endpoint win). CARE-PATH supports a smaller real-world effect with imperfect "
        "implementation. CONNECT-OBS supports directionally similar associations but cannot "
        "alone justify causal policy claims."
    )
    pdf.subhead("Agreements")
    pdf.bullet("All three sources report improved adherence signals under coaching-like interventions.")
    pdf.bullet("No study reports a major safety signal tied to coaching itself.")
    pdf.subhead("Conflicts / tensions")
    pdf.bullet("ADHERE-1 shows meaningful HbA1c improvement; CARE-PATH does not.")
    pdf.bullet("Effect magnitude is larger in tightly controlled RCT settings than in pragmatic/observational settings.")
    pdf.bullet("Engagement appears necessary for benefit (CONNECT-OBS), but ADHERE-1 did not pre-specify engagement mediation.")
    pdf.subhead("Evidence quality ranking (for agent reasoning)")
    pdf.bullet("1) ADHERE-1 for internal validity and causal inference.")
    pdf.bullet("2) CARE-PATH for external validity of lighter-touch deployment.")
    pdf.bullet("3) CONNECT-OBS for hypothesis generation and subgroup signals only.")

    pdf.add_page()
    pdf.section("7. Ontology Hints for Weave")
    pdf.body(
        "When Weave discovers ontology from this document, useful entity classes include: Study, "
        "Population, Intervention, Comparator, Endpoint, Finding, Limitation, Site, and EvidenceGrade. "
        "Useful relationships include: Study-evaluates-Intervention, Study-reports-Finding, "
        "Finding-supports-or-conflicts-with-Finding, and Limitation-constrains-Finding."
    )
    pdf.bullet("Entities: ADHERE-1, CARE-PATH, CONNECT-OBS, MPR, HbA1c, PAM-13, adaptive coaching, SMS nudges.")
    pdf.bullet("Attributes: sample size, follow-up duration, confidence intervals, p-values, bias risks.")
    pdf.bullet("Tags to consider: research, evidence-synthesis, adherence, cardiometabolic, rct, observational.")

    pdf.section("8. Agent / Test-with-LLM Answer Contract")
    pdf.body(
        "For Research Knowledge Fabrics, answers should: (1) ground claims in study text, "
        "(2) separate result from interpretation, (3) call out design limitations, (4) compare "
        "across studies when asked, and (5) refuse to invent statistics not present in the corpus."
    )
    pdf.body(
        "Example grounded answer pattern: Summary -> Evidence by study -> Agreements/conflicts -> "
        "Limitations -> Open questions. Weave's Research intelligence profile is designed to "
        "enforce this stance for complex multi-hop queries."
    )

    pdf.section("9. Demo Checklist")
    pdf.bullet("Create Knowledge Fabric and select Research Knowledge Fabric.")
    pdf.bullet("Upload this PDF and complete fabric creation.")
    pdf.bullet("Confirm fabric card shows Research Knowledge Fabric intelligence.")
    pdf.bullet("In Test with LLM, ask a comparative synthesis question across Study A/B/C.")
    pdf.bullet("Verify the answer cites study names, notes conflicts, and states limitations.")

    pdf.output(str(OUTPUT))
    return OUTPUT


if __name__ == "__main__":
    path = build()
    print(f"Wrote {path}")
