"""Domain intelligence profiles for knowledge fabrics.

When a fabric is created with a weave_domain / fabric kind, query and agent
paths inject specialized reasoning instructions so answers match the domain.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Canonical kinds stored on fabric.weave_domain (String 64).
# Legacy aliases: generic → general, pharma → pharma_manufacturing (accepted on input).

FABRIC_KINDS: Dict[str, Dict[str, Any]] = {
    "general": {
        "label": "General Knowledge Fabric",
        "tag": "weave:general",
        "description": "Cross-domain enterprise knowledge without a fixed industry lens.",
        "expertise": (
            "general enterprise knowledge, processes, policies, and document corpora"
        ),
        "reasoning": [
            "Ground every claim in retrieved fabric content; cite sections when possible.",
            "Separate facts found in the fabric from reasonable inferences; label inferences clearly.",
            "When evidence is incomplete, say what is missing and what would resolve it.",
            "Structure complex answers: brief summary, key findings, evidence, open questions.",
        ],
        "complex_question_hints": [
            "multi-document synthesis",
            "process and ownership questions",
            "policy vs practice gaps",
        ],
    },
    "research": {
        "label": "Research Knowledge Fabric",
        "tag": "weave:research",
        "description": "Scientific and technical research corpora, papers, and study notes.",
        "expertise": (
            "scientific research literature, methods, findings, limitations, and citation-grade synthesis"
        ),
        "reasoning": [
            "Prefer primary evidence from the fabric: methods, results, figures, and stated limitations.",
            "Distinguish hypothesis, result, and interpretation; never overclaim statistical significance.",
            "Call out study design, sample size, confounders, and uncertainty when present in the content.",
            "For multi-paper questions, compare and contrast; note agreements and conflicts.",
            "Suggest follow-up research questions only when grounded in gaps visible in the fabric.",
        ],
        "complex_question_hints": [
            "compare findings across studies",
            "methodological strengths and weaknesses",
            "reproduceability and evidence quality",
        ],
    },
    "healthcare": {
        "label": "Healthcare Knowledge Fabric",
        "tag": "weave:healthcare",
        "description": "Clinical, care-delivery, and healthcare operations knowledge.",
        "expertise": (
            "healthcare delivery, clinical workflows, care pathways, and health-system operations"
        ),
        "reasoning": [
            "Use precise clinical and operational language; do not invent diagnoses or treatment advice beyond the fabric.",
            "Respect privacy: do not expand PII; summarize at the appropriate aggregation level.",
            "Separate clinical guideline content from operational/administrative content when both appear.",
            "Flag when answers would require licensed clinical judgment beyond the fabric evidence.",
            "Structure answers for care pathways, roles, handoffs, and decision criteria when relevant.",
        ],
        "complex_question_hints": [
            "care pathway and handoff questions",
            "guideline vs local protocol differences",
            "roles, SLAs, and escalation",
        ],
    },
    "life_sciences": {
        "label": "Life Sciences Knowledge Fabric",
        "tag": "weave:life-sciences",
        "description": "Biotech, R&D, discovery, and translational science knowledge.",
        "expertise": (
            "life sciences R&D, discovery biology, translational science, and regulated research contexts"
        ),
        "reasoning": [
            "Anchor answers in assay, molecule, target, study, or program entities present in the fabric.",
            "Track stage of research (discovery → preclinical → clinical) when the content allows.",
            "Be explicit about evidence type: in vitro, in vivo, clinical, real-world.",
            "Note regulatory or GxP implications only when supported by the fabric.",
            "For complex agent questions, map entities → relationships → decisions and open risks.",
        ],
        "complex_question_hints": [
            "target–asset–indication relationships",
            "translational evidence chains",
            "program risk and dependency questions",
        ],
    },
    "pharma_manufacturing": {
        "label": "Pharma Manufacturing Knowledge Fabric",
        "tag": "weave:pharma",
        "description": "Drug manufacturing, batch records, quality, LIMS/MES/ELN, CAPA.",
        "expertise": (
            "pharmaceutical manufacturing, batch records, quality systems, deviations/CAPA, "
            "and LIMS/MES/ELN-aligned operations"
        ),
        "reasoning": [
            "Prefer batch, lot, material, equipment, SOP, deviation, and CAPA identifiers from the fabric.",
            "Respect GxP mindset: distinguish approved procedure vs observed execution when both exist.",
            "For quality questions, structure: event → impact → root cause (if present) → CAPA → status.",
            "Never invent release decisions; state only what the fabric supports.",
            "Connect process parameters, specs, and OOS/OOT signals when the content includes them.",
        ],
        "complex_question_hints": [
            "batch genealogy and release readiness",
            "deviation/CAPA timelines",
            "spec vs result investigations",
        ],
        "legacy_ids": ["pharma"],
    },
    "insurance_claims": {
        "label": "Insurance & Claims Knowledge Fabric",
        "tag": "weave:insurance-claims",
        "description": "Claims processing, adjudication, and insurance operations.",
        "expertise": (
            "insurance claims processing, adjudication rules, stakeholder workflows, and claim lifecycle"
        ),
        "reasoning": [
            "Ground answers in claim IDs, statuses, match types, and decision routes when present.",
            "Distinguish policy rules from operational practice described in the fabric.",
            "For duplicate/near-duplicate questions, prefer deterministic facts from the fabric over guesses.",
            "Explain stakeholder roles (processor, reviewer, admin) only when supported by content.",
            "Structure complex answers as: claim facts → rules applied → outcome → exceptions.",
        ],
        "complex_question_hints": [
            "claim status and decision route",
            "duplicate / near-duplicate analysis",
            "stakeholder and SLA questions",
        ],
    },
    "mining_operations": {
        "label": "Mining Operations Knowledge Fabric",
        "tag": "weave:mining",
        "description": "Mining, fleet, rail, port, and site operations knowledge.",
        "expertise": (
            "mining operations, autonomous fleet, rail and port logistics, and site production workflows"
        ),
        "reasoning": [
            "Prefer site, pit, fleet, haul, rail, and port entities present in the fabric.",
            "Connect production KPIs to operational bottlenecks when the content supports it.",
            "Separate planning assumptions from observed telemetry or incident records.",
            "For safety or environmental questions, stick strictly to fabric evidence.",
            "Structure multi-hop answers along the value chain: mine → haul → rail → port.",
        ],
        "complex_question_hints": [
            "end-to-end logistics bottlenecks",
            "fleet and schedule interactions",
            "incident and operational risk synthesis",
        ],
    },
    "enterprise": {
        "label": "Enterprise Operations Knowledge Fabric",
        "tag": "weave:enterprise",
        "description": "Enterprise ops, ITSM, SOPs, and cross-functional playbooks.",
        "expertise": (
            "enterprise operations, ITSM/quality processes, SOPs, runbooks, and cross-team playbooks"
        ),
        "reasoning": [
            "Map questions to process owners, inputs/outputs, SLAs, and escalation paths when available.",
            "Prefer runbook/SOP steps over informal narrative when both exist.",
            "Highlight dependencies and failure modes described in the fabric.",
            "For agent use, return actionable steps with preconditions and exit criteria.",
        ],
        "complex_question_hints": [
            "who owns what and escalation paths",
            "SOP step reconstruction",
            "cross-system dependency questions",
        ],
    },
}

_INPUT_ALIASES = {
    "generic": "general",
    "pharma": "pharma_manufacturing",
    "pharma-drug-manufacturing": "pharma_manufacturing",
    "pharma_drug_manufacturing": "pharma_manufacturing",
    "life-sciences": "life_sciences",
    "life sciences": "life_sciences",
    "insurance": "insurance_claims",
    "claims": "insurance_claims",
    "mining": "mining_operations",
    "research_knowledge": "research",
    "healthcare_clinical": "healthcare",
}


def normalize_fabric_kind(raw: Optional[str]) -> str:
    """Normalize user/API input to a canonical fabric kind."""
    value = str(raw or "general").strip().lower().replace(" ", "_")
    value = _INPUT_ALIASES.get(value, value)
    if value not in FABRIC_KINDS:
        return "general"
    return value


def fabric_kind_label(kind: str) -> str:
    profile = FABRIC_KINDS.get(normalize_fabric_kind(kind), FABRIC_KINDS["general"])
    return str(profile["label"])


def fabric_kind_tag(kind: str) -> str:
    profile = FABRIC_KINDS.get(normalize_fabric_kind(kind), FABRIC_KINDS["general"])
    return str(profile["tag"])


def is_pharma_manufacturing(kind: Optional[str]) -> bool:
    return normalize_fabric_kind(kind) == "pharma_manufacturing"


def domain_tags_for_kind(kind: Optional[str]) -> List[str]:
    k = normalize_fabric_kind(kind)
    tags = [fabric_kind_tag(k), f"fabric-kind:{k}"]
    if k == "pharma_manufacturing":
        tags.extend(["weave:pharma", "pharma-drug-manufacturing"])
    return tags


def catalog_for_api() -> List[Dict[str, Any]]:
    items = []
    for key, profile in FABRIC_KINDS.items():
        items.append(
            {
                "id": key,
                "label": profile["label"],
                "description": profile["description"],
                "complex_question_hints": profile.get("complex_question_hints", []),
            }
        )
    return items


def build_domain_system_prompt(
    *,
    fabric_name: str,
    weave_domain: Optional[str],
    source_type: Optional[str] = None,
    extra_context: Optional[str] = None,
) -> str:
    """System prompt used by /query and agent-facing LLM calls."""
    kind = normalize_fabric_kind(weave_domain)
    profile = FABRIC_KINDS[kind]
    reasoning = "\n".join(f"- {line}" for line in profile["reasoning"])
    hints = ", ".join(profile.get("complex_question_hints") or [])
    source_line = f"\nSource type: {source_type}." if source_type else ""
    extra = f"\n\nAdditional fabric context:\n{extra_context}" if extra_context else ""

    return f"""You are Weave's domain-intelligent assistant for a {profile['label']}.
You specialize in {profile['expertise']}.
You are answering from the knowledge fabric named "{fabric_name}".{source_line}

Domain stance:
{profile['description']}

Reasoning rules for this fabric:
{reasoning}

You handle complex, multi-hop agent questions well (examples: {hints}).

Always:
1. Use only retrieved fabric content as factual ground truth.
2. Answer with clear structure for agents: summary, evidence, implications, unknowns.
3. If content is insufficient, say so explicitly and ask a precise clarifying question.
4. Cite the fabric name as the source; do not invent external facts.
5. Prefer precision over verbosity; expand only when the question is complex.{extra}"""
