#!/usr/bin/env python3
"""Generate generic mining operations PDF for Weave Knowledge Fabric demo."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

OUTPUT = Path(__file__).resolve().parent / "Weave_Mining_Operations_Knowledge_Fabric_Guide.pdf"


class MiningGuidePDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(90, 100, 120)
        self.cell(
            0,
            8,
            "Weave Knowledge Fabric | Mining Operations Use Case | TCS",
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
        self.set_fill_color(62, 207, 155)
        self.rect(0, 0, 210, 6, style="F")
        self.set_y(48)
        self.set_font("Helvetica", "B", 26)
        self.set_text_color(255, 255, 255)
        self.multi_cell(0, 13, "Mining Operations\nKnowledge Fabric", align="C")
        self.ln(6)
        self.set_font("Helvetica", "", 13)
        self.set_text_color(148, 163, 184)
        self.multi_cell(
            0,
            7,
            "Comprehensive use case for ontology-driven fabric creation\n"
            "Iron ore operations, autonomous fleet, processing, rail, port and green energy",
            align="C",
        )
        self.ln(14)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(94, 200, 242)
        self.cell(0, 8, "TCS Weave - Hybrid Retrieval Intelligence Platform", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(180, 190, 210)
        self.cell(0, 8, "Enterprise Mining Demo | " + datetime.now().strftime("%B %Y"), align="C")
        self.ln(20)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(139, 156, 176)
        self.multi_cell(
            0,
            5,
            "Upload this document to Weave to instantiate a Super Knowledge Fabric with "
            "discovered ontology, canonical knowledge graph, LLM executive insights, "
            "and agent-ready grounded retrieval.",
            align="C",
        )

    def section(self, title: str):
        self.set_x(self.l_margin)
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(15, 23, 42)
        self.multi_cell(0, 7, title)
        self.set_draw_color(62, 207, 155)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def sub(self, title: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(30, 58, 95)
        self.multi_cell(0, 6, title)
        self.ln(1)

    def body(self, text: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(30, 41, 59)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def bullet(self, text: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(30, 41, 59)
        self.multi_cell(0, 5, f"  -  {text}")

    def table_header(self, cols: list[tuple[str, int]]):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(241, 245, 249)
        self.set_text_color(15, 23, 42)
        for label, width in cols:
            self.cell(width, 6.5, label, border=1, fill=True)
        self.ln()

    def table_row(self, cols: list[tuple[str, int]], small: bool = False):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 7.5 if small else 8)
        self.set_text_color(51, 65, 85)
        for label, width in cols:
            self.cell(width, 5.5 if small else 6, str(label)[:56], border=1)
        self.ln()


def build() -> Path:
    pdf = MiningGuidePDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.cover()

    pdf.add_page()
    pdf.section("1. Executive Summary")
    pdf.body(
        "Large-scale integrated iron ore mining combines open-pit extraction, autonomous haulage, "
        "ore processing, heavy-haul rail, and port export into a single operating system. Many producers "
        "also run parallel decarbonisation and renewable energy programs. Operational data spans SCADA "
        "historians, fleet management systems (FMS), maintenance (SAP PM), safety (ICAM), environmental "
        "monitoring, production planning, and engineering document repositories.\n\n"
        "This guide defines a Mining Operations domain model for TCS Weave Knowledge Fabric. "
        "When uploaded, Weave performs multi-stage fabric creation: document chunking and vector indexing, "
        "ontology discovery (entities, attributes, relationships), ontology enrichment via LLM (Bedrock/OpenAI), "
        "canonical knowledge graph build, exploratory co-occurrence graph, LLM executive insight briefing, "
        "and agent-ready retrieval APIs. The result is a Super Knowledge Fabric - not a simple chatbot index, "
        "but a governed semantic layer connecting pits, assets, production, maintenance, safety, and export logistics."
    )

    pdf.section("2. Business Challenge at Mining Enterprise Scale")
    pdf.bullet("Siloed operational knowledge across mine sites, processing, rail, port, and energy programs.")
    pdf.bullet("Engineers and planners spend hours reconciling equipment IDs, shift logs, maintenance history, and production KPIs.")
    pdf.bullet("Autonomous fleet incidents require rapid cross-system reasoning (FMS + maintenance + geotechnical + safety).")
    pdf.bullet("Regulatory and sustainability reporting demands traceable evidence from heterogeneous sources.")
    pdf.bullet("AI copilots fail when retrieval is shallow - relationships between assets, routes, and production targets are lost.")
    pdf.ln(2)
    pdf.body(
        "Weave addresses this with Hybrid Retrieval Intelligence: classic RAG speed plus graph-aware ontology "
        "enrichment and secure APIs for enterprise agents."
    )

    pdf.section("3. Weave Super Knowledge Fabric - What Mining Operations Get")
    pdf.table_header([("Capability", 55), ("Outcome for Mining Ops", 135)])
    rows = [
        ("Knowledge Fabric", "Domain-scoped Mining Ops fabric with guardrails (classification, PII, compliance tags)"),
        ("Ontology Discovery", "Auto-extracted entities: MineSite, HaulTruck, Crusher, Train, PortShipment, WorkOrder"),
        ("Ontology Enrichment", "LLM maps field synonyms, business definitions, and governance recommendations"),
        ("Canonical Graph", "Approved entity-relationship graph for schema-aware retrieval"),
        ("Exploratory Graph", "Co-occurrence graph from documents for discovery workshops"),
        ("Knowledge Graph UI", "Interactive D3 visualization with LLM executive briefing"),
        ("Grounded Retrieval", "Evidence-first context for shift handover, RCA, and planning agents"),
        ("Test with LLM", "Natural-language Q&A over fabric with Bedrock Claude or OpenAI"),
        ("Agent APIs", "Partner/agent integration via secured REST endpoints"),
        ("Composite Fabrics", "Merge mine + rail + port PDFs/CSVs into unified Super KF"),
    ]
    for a, b in rows:
        pdf.table_row([(a, 55), (b, 135)])

    pdf.add_page()
    pdf.section("4. Mining Domain Scope")
    pdf.sub("4.1 Physical Operations (Iron Ore Value Chain)")
    pdf.bullet("Mine hubs: North Ridge, Central Range, Western Plateau, Iron Bridge Hub (reference labels).")
    pdf.bullet("Open pit mining: drill and blast, load and haul, grade control, dewatering.")
    pdf.bullet("Processing: primary/secondary crushers, ore processing facility (OPF), stockpiles, blending.")
    pdf.bullet("Rail: autonomous and conventional ore trains, track maintenance, cycle time KPIs.")
    pdf.bullet("Port: train unloaders, stockyards, shiploaders, vessel scheduling, export tonnes.")
    pdf.ln(1)
    pdf.sub("4.2 Autonomous and Digital Systems")
    pdf.bullet("Autonomous Haulage System (AHS): haul trucks, health events, intervention logs, geofencing.")
    pdf.bullet("Fleet Management System (FMS): dispatch, queue times, payload, fuel, cycle segments.")
    pdf.bullet("Condition monitoring: vibration, temperature, oil analysis, predictive maintenance scores.")
    pdf.ln(1)
    pdf.sub("4.3 Sustainability and Green Energy")
    pdf.bullet("Green hydrogen projects, renewable generation assets, scope 1/2/3 emissions tracking.")
    pdf.bullet("Environmental approvals, water stewardship, rehabilitation plans, tailings governance.")

    pdf.section("5. End-to-End Operational Lifecycle")
    pdf.body(
        "Stage 1 - Mine Planning: geological model, blast design, dig plan, fleet allocation, production target "
        "for shift (target_tonnes, target_fe_grade).\n\n"
        "Stage 2 - Extraction: drilling program executed, blast fired, excavator loads haul truck, payload "
        "verified by onboard systems, cycle time recorded (load_queue_min, haul_min, dump_min).\n\n"
        "Stage 3 - Processing: ore delivered to crusher, throughput tph recorded, downtime events logged "
        "(downtime_code, root_cause_category), product stockpile updated.\n\n"
        "Stage 4 - Rail and Port: train consist assembled, rail cycle to port, stockpile blending, vessel load "
        "commenced, bill of lading reference assigned, export_confirmed_date.\n\n"
        "Stage 5 - Maintenance and Reliability: work order raised (PM or breakdown), parts reserved, technician "
        "assigned, MTTR/MTBF updated, return to service.\n\n"
        "Stage 6 - Safety and Governance: incident reported (ICAM), investigation status, corrective actions, "
        "regulatory notification if required, audit trail to governance_status."
    )

    pdf.add_page()
    pdf.section("6. Ontology Entity Catalog (Discovered and Enriched)")
    pdf.body(
        "Weave Ontology Discovery scans this document and linked sources to propose the following entity types. "
        "Analysts review, approve, and version the canonical ontology before graph build."
    )
    pdf.table_header([("Entity", 42), ("Description", 98), ("Key Identifier", 50)])
    entities = [
        ("MineSite", "Operational mine or hub with pits and processing", "site_id e.g. SITE-NR"),
        ("OpenPit", "Active pit or stage within a mine site", "pit_id e.g. NR-NORTH-03"),
        ("AutonomousHaulTruck", "AHS-enabled haul unit", "asset_id e.g. AHT-2147"),
        ("Excavator", "Loading unit (electric or diesel)", "asset_id e.g. EX-8831"),
        ("HaulCycle", "Single load-haul-dump cycle event", "cycle_id"),
        ("Crusher", "Primary/secondary crushing asset", "crusher_id"),
        ("ProcessingPlant", "OPF or beneficiation facility", "plant_id"),
        ("Stockpile", "Blended or product stockpile", "stockpile_id"),
        ("OreTrain", "Rail consist moving ore to port", "train_id / consist_id"),
        ("RailSegment", "Track segment with maintenance history", "segment_id"),
        ("PortTerminal", "Export terminal facility", "terminal_id"),
        ("VesselShipment", "Export shipment to customer", "shipment_id / BL_ref"),
        ("ProductionTarget", "Shift/day production plan", "target_id"),
        ("SensorReading", "Telemetry point-in-time", "reading_id"),
        ("MaintenanceWorkOrder", "SAP PM or equivalent WO", "wo_number"),
        ("SparePart", "Inventory part linked to WO", "part_number"),
        ("SafetyIncident", "Safety/health/environment event", "incident_id"),
        ("PermitToWork", "Controlled work authorization", "ptw_id"),
        ("EnvironmentalMonitor", "Air/water/noise monitoring station", "monitor_id"),
        ("OreGradeSample", "Assay / grade control sample", "sample_id"),
        ("HydrogenProject", "Green energy initiative", "project_id"),
        ("Operator", "Human operator or controller role", "employee_id"),
        ("ShiftLog", "Shift handover narrative", "shift_id"),
    ]
    for e, d, k in entities:
        pdf.table_row([(e, 42), (d, 98), (k, 50)], small=True)

    pdf.section("7. Ontology Relationship Model")
    pdf.table_header([("Relationship", 52), ("From -> To", 55), ("Business meaning", 83)])
    rels = [
        ("CONTAINS", "MineSite -> OpenPit", "Site owns pit geometry and plan"),
        ("OPERATES", "Operator -> ShiftLog", "Controller accountable for shift"),
        ("ASSIGNED_TO", "AutonomousHaulTruck -> HaulCycle", "Truck executes cycle"),
        ("LOADS_FROM", "Excavator -> OpenPit", "Material source for loading"),
        ("TRANSPORTS_TO", "HaulCycle -> Crusher", "Ore movement path"),
        ("FEEDS", "Crusher -> ProcessingPlant", "Plant feed stream"),
        ("STORES_IN", "ProcessingPlant -> Stockpile", "Product placement"),
        ("LOADS", "OreTrain -> Stockpile", "Rail loading event"),
        ("DELIVERS_TO", "OreTrain -> PortTerminal", "Rail cycle completion"),
        ("EXPORTS_VIA", "VesselShipment -> PortTerminal", "Ship loading"),
        ("MONITORS", "SensorReading -> AutonomousHaulTruck", "Condition telemetry"),
        ("RAISES", "MaintenanceWorkOrder -> AutonomousHaulTruck", "Asset maintenance"),
        ("CONSUMES", "MaintenanceWorkOrder -> SparePart", "Parts usage"),
        ("OCCURS_AT", "SafetyIncident -> MineSite", "Incident location"),
        ("REQUIRES", "PermitToWork -> MaintenanceWorkOrder", "Safety control"),
        ("SAMPLES", "OreGradeSample -> OpenPit", "Grade control loop"),
        ("TARGETS", "ProductionTarget -> MineSite", "Plan vs actual"),
        ("GOVERNS", "EnvironmentalMonitor -> MineSite", "Compliance monitoring"),
        ("PART_OF", "HydrogenProject -> MineSite", "Decarbonisation linkage"),
    ]
    for r, f, m in rels:
        pdf.table_row([(r, 52), (f, 55), (m, 83)], small=True)

    pdf.add_page()
    pdf.section("8. Core Attribute Dictionary (Ontology Enrichment Targets)")
    pdf.body(
        "Ontology Enrichment maps operational field names from SCADA, FMS, SAP, and PDFs to canonical attributes below."
    )
    pdf.table_header([("Attribute", 45), ("Type", 22), ("Domain usage", 123)])
    attrs = [
        ("target_tonnes", "decimal", "Shift production target (wet/dry tonnes)"),
        ("target_fe_grade", "decimal", "Target iron grade %Fe"),
        ("payload_tonnes", "decimal", "Actual truck payload"),
        ("cycle_time_min", "decimal", "Total load-haul-dump minutes"),
        ("availability_pct", "decimal", "Asset availability rolling 24h"),
        ("utilisation_pct", "decimal", "Scheduled vs operating time"),
        ("downtime_code", "string", "Standard downtime reason code"),
        ("root_cause_category", "enum", "Equipment / Process / Weather / Safety"),
        ("mttr_hours", "decimal", "Mean time to repair"),
        ("mtbf_hours", "decimal", "Mean time between failures"),
        ("fe_grade_pct", "decimal", "Assayed iron content"),
        ("silica_pct", "decimal", "Impurity for blending"),
        ("moisture_pct", "decimal", "Ore moisture for tonnage correction"),
        ("train_cycle_hours", "decimal", "Mine-to-port rail cycle"),
        ("vessel_deadweight", "decimal", "Ship capacity tonnes"),
        ("export_tonnes", "decimal", "Final shipped quantity"),
        ("incident_severity", "enum", "Near miss / LTI / environmental"),
        ("icam_status", "enum", "Investigation workflow state"),
        ("governance_status", "enum", "Logged / Approved / Escalated"),
        ("sensitivity_level", "enum", "Public / Internal / Confidential / Restricted"),
        ("data_classification", "enum", "Fabric guardrail classification"),
        ("llm_reasoning_used", "boolean", "Agent used LLM for RCA or planning"),
        ("confidence_band", "enum", "Low / Medium / High for automated insights"),
    ]
    for a, t, u in attrs:
        pdf.table_row([(a, 45), (t, 22), (u, 123)], small=True)

    pdf.section("9. Detailed Scenario - Autonomous Haul Truck Intervention (AHT-2147)")
    pdf.body(
        "On 2026-03-14 night shift at North Ridge Mine, Autonomous Haul Truck AHT-2147 recorded elevated brake temperature "
        "on SensorReading SR-991022 (value 118 deg C, threshold 105 deg C). FMS flagged health_event_code BRAKE_TEMP_HIGH. "
        "Fleet controller created ShiftLog SL-20260314-N2 noting reduced fleet speed in Pit NR-NORTH-03. "
        "MaintenanceWorkOrder WO-4509821 raised with priority 1; SparePart PN-BRK-7720 reserved. "
        "PermitToWork PTW-88341 required for ground intervention. MTTR target 4h; actual return_to_service 3.2h. "
        "ProductionTarget TG-20260314-NR reduced by 12,000 tonnes due to 2-truck fleet derate. "
        "SafetyIncident not raised (controlled stop). governance_status: Logged. sensitivity_level: Internal. "
        "LLM reasoning summary: Root cause likely brake pad wear; recommend inspection of entire AHT-214x series."
    )

    pdf.section("10. Detailed Scenario - Port Export and Blending")
    pdf.body(
        "VesselShipment SHP-2026-8841 (customer: major steel mill) requires fe_grade_pct >= 62.0 and silica_pct <= 4.2. "
        "PortTerminal Export Berth A blends Stockpile STK-B1 (high Fe) with STK-B2 (medium Fe) to meet specification. "
        "OreTrain OT-4472 delivers 24,000 wet tonnes from Central Range rail cycle RC-9912 (cycle_time 18.4h). "
        "Shiploader SL-02 loads vessel hold 3; export_tonnes confirmed 178,400. Bill of lading BL-OPS-2026-8841 issued. "
        "EnvironmentalMonitor EM-PORT-07 records dust PM10 within limit. audit_id AUD-2026-4412 logged for export compliance."
    )

    pdf.add_page()
    pdf.section("11. How to Create the Mining Super Knowledge Fabric in Weave")
    pdf.sub("Step 1 - Sign in and permissions")
    pdf.body("Login as admin or user with Create Knowledge, Ontology, and Fabrics features enabled.")
    pdf.sub("Step 2 - Upload this PDF")
    pdf.body(
        "Navigate to Create Knowledge -> Upload PDF. Name the fabric: Mining Operations. "
        "Add tags: mining, iron-ore, autonomous-fleet, rail, port. Set weave_domain: generic."
    )
    pdf.sub("Step 3 - Wait for fabric build")
    pdf.body("Progress: ingest -> chunk -> embed -> index. document_count and total_chunks populate on completion.")
    pdf.sub("Step 4 - Ontology Discovery")
    pdf.body(
        "Open fabric -> Platform panel -> Discover Ontology. Weave extracts entities (Section 6) and relationships "
        "(Section 7) using LLM-assisted discovery. Review proposed elements in Ontology Workspace."
    )
    pdf.sub("Step 5 - Review, enrich, approve")
    pdf.body(
        "Ontology Enrichment recommends attribute mappings, synonyms (e.g. truck_id -> asset_id), and governance. "
        "Approve version -> Build Canonical Graph."
    )
    pdf.sub("Step 6 - Explore Super KF")
    pdf.body(
        "View Knowledge Graph: canonical + exploratory views, LLM Executive Insight briefing, entity analytics. "
        "Test with LLM using Bedrock Claude Sonnet 4.5 or OpenAI."
    )
    pdf.sub("Step 7 - Optional composite")
    pdf.body(
        "Add CSV exports (production actuals, maintenance WOs) or codebase fabric (FMS integration repo) "
        "and merge into composite Super KF for cross-source retrieval."
    )

    pdf.section("12. Composite Fabric Architecture for Mining")
    pdf.body(
        "Recommended multi-fabric layout for enterprise rollout:\n\n"
        "Fabric A - Operations Reference (this PDF + engineering standards).\n"
        "Fabric B - Production and KPI CSV from data lake (Snowflake/Databricks connector).\n"
        "Fabric C - Maintenance and SAP PM work order extracts.\n"
        "Fabric D - Safety and ICAM investigation library.\n"
        "Fabric E - Sustainability / green energy policy documents.\n"
        "Fabric F - Codebase / integration APIs (optional, for agent developers).\n\n"
        "Weave composite fabric merges retrieval across sources while preserving per-fabric guardrails."
    )

    pdf.section("13. Agent and Copilot Query Examples")
    queries = [
        "What is the end-to-end lifecycle from pit extraction to vessel export?",
        "Explain relationships between AutonomousHaulTruck, HaulCycle, and MaintenanceWorkOrder.",
        "What ontology attributes define production target vs actual for a shift?",
        "Describe the intervention workflow when brake temperature exceeds threshold on AHT-2147.",
        "How does Weave canonical graph differ from exploratory graph for mine planning?",
        "What governance fields apply to safety incidents and export compliance audits?",
        "Which entities are involved in port blending to meet fe_grade_pct specification?",
        "How should agents use grounded retrieval before invoking LLM for RCA?",
        "What is the recommended composite fabric strategy for multi-site mining operations?",
        "List downtime_code categories and root_cause_category values for processing plants.",
    ]
    for q in queries:
        pdf.bullet(q)

    pdf.add_page()
    pdf.section("14. Operational KPI Reference")
    pdf.table_header([("KPI", 50), ("Formula / definition", 90), ("Typical owner", 50)])
    kpis = [
        ("Availability", "Operating hours / scheduled hours", "Maintenance"),
        ("Utilisation", "Productive time / available time", "Production"),
        ("Cycle time", "Load + haul + dump + queue", "Mining"),
        ("Payload compliance", "Actual vs target payload %", "Mining"),
        ("Throughput (tph)", "Tonnes processed per hour", "Processing"),
        ("Rail cycle time", "Departure mine to port arrival", "Rail"),
        ("Stockpile variance", "Model vs survey tonnes", "Port"),
        ("Fe grade variance", "Assay vs target grade", "Geology"),
        ("MTTR", "Repair duration mean", "Maintenance"),
        ("LTIFR", "Lost time injuries per hours", "Safety"),
        ("Scope 1 intensity", "tCO2e per tonne shipped", "Sustainability"),
    ]
    for k, f, o in kpis:
        pdf.table_row([(k, 50), (f, 90), (o, 50)])

    pdf.section("15. Governance, Guardrails and Security")
    pdf.bullet("data_classification: Restricted for production telemetry; Confidential for commercial export data.")
    pdf.bullet("pii_fields: operator employee_id masked in partner-facing APIs.")
    pdf.bullet("compliance_tags: WHS, EPA, ISO45001, ISO14001 where applicable.")
    pdf.bullet("encryption_at_rest / encryption_in_transit: enabled on fabric guardrails profile.")
    pdf.bullet("approved_roles: mine_controller, maintenance_planner, port_logistics, safety_advisor.")
    pdf.bullet("ontology version approval: no runtime graph mutation without approved ontology version.")
    pdf.ln(2)

    pdf.section("16. Expected Super KF Outputs (Weave Platform)")
    pdf.table_header([("Output", 50), ("Description", 140)])
    outputs = [
        ("Vector index", "Semantic chunks from this guide + uploaded supplements"),
        ("Ontology project", "Versioned entity/attribute/relationship catalog"),
        ("Canonical graph", "Approved schema graph for deterministic retrieval"),
        ("Exploratory graph", "Co-occurrence graph for discovery sessions"),
        ("LLM insight", "Executive briefing: Executive Summary, Key Insights, Recommendations"),
        ("Retrieval API", "POST /query and /retrieve with evidence citations"),
        ("Graph export", "JSON export for downstream graph analytics"),
        ("Migration JSON", "If codebase fabric added - modernization blueprint package"),
    ]
    for a, b in outputs:
        pdf.table_row([(a, 50), (b, 140)])

    pdf.section("17. Mining Value Proposition with TCS Weave")
    pdf.body(
        "Speed: First Super KF from this document in hours, not months of graph modeling.\n"
        "Depth: Ontology + graph enrichment captures relationships plain RAG misses (truck -> WO -> pit -> target).\n"
        "Control: Human-in-the-loop ontology approval, fabric guardrails, audit trails.\n"
        "Flexibility: Bedrock on AWS for enterprise LLM; OpenAI for dev; agent APIs for mining copilots.\n"
        "Scale: Composite fabrics across mine, rail, port, and energy programs; deploy on-prem, EC2, or AWS with IAM Bedrock.\n\n"
        "Weave is the Hybrid Retrieval Intelligence Platform - Classic RAG core, graph-aware ontology enrichment, "
        "and secure agent-ready APIs - engineered for integrated mining and green energy operations."
    )

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(100, 116, 139)
    pdf.multi_cell(
        0,
        5,
        "Document version 1.0 | TCS Weave Knowledge Fabric | Mining operations demonstration and fabric creation. "
        "Site and asset names are illustrative for ontology modeling.",
    )

    pdf.output(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    path = build()
    print(f"Created: {path}")
