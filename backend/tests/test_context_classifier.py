"""Correction classification and the approved contract that the next envelope reads."""
from app.models.ontology import (
    OntologyAttribute,
    OntologyClass,
    OntologyConstraint,
    OntologyConstraintType,
    OntologyElementStatus,
    OntologyVersion,
)
from app.services import agent_memory_service
from app.services.context.classifier import classify_correction
from app.services.context.promote import approved_contract_lines, approved_rules_for_discovery


CLASSES = [
    {"name": "Members", "id": "cls_members"},
    {"name": "CareEvents", "id": "cls_events"},
]
ATTRIBUTES = [{"name": "priority", "id": "attr_priority", "class_name": "Members"}]
COLUMNS = ["care_manager", "adherence"]


def test_alias_rule_value_and_session_go_to_different_destinations():
    alias = classify_correction("P1 means priority", classes=CLASSES, attributes=ATTRIBUTES, columns=COLUMNS)
    assert alias["destination"] == "ontology_alias"
    assert alias["alias"] == "P1"
    assert alias["attribute_name"] == "priority"

    rule = classify_correction(
        "For COPD, call the care manager when an ER event is inside 14 days, even if adherence is above the threshold.",
        classes=CLASSES,
        attributes=ATTRIBUTES,
        columns=COLUMNS,
    )
    assert rule["destination"] == "ontology_constraint"
    assert rule["related_entity"] == "CareEvents"

    value = classify_correction(
        "Lisa's care manager is Anita Shah",
        classes=CLASSES,
        attributes=ATTRIBUTES,
        columns=COLUMNS,
    )
    assert value["destination"] == "memory"

    session = classify_correction(
        "Only for this conversation, skip the call.",
        classes=CLASSES,
        attributes=ATTRIBUTES,
        columns=COLUMNS,
    )
    assert session["destination"] == "session"

    vague = classify_correction("status means adjudication_status")
    assert vague["destination"] == "memory"


def test_later_episode_discards_the_correction():
    found = classify_correction(
        "Call within 14 days",
        later_texts=["Do not call within 14 days"],
    )
    assert found["destination"] == "discard"


def test_approved_version_contributes_rules_to_the_envelope_and_the_next_discovery():
    version = OntologyVersion(
        id="ver_approved",
        project_id="proj_1",
        version_label="1.0",
        is_draft=False,
        classes=[OntologyClass(id="cls_events", name="CareEvents", normalized_name="CareEvents")],
        attributes=[
            OntologyAttribute(
                id="attr_priority",
                class_id="cls_events",
                attribute_name="priority",
                normalized_name="priority",
                aliases=["P1"],
                status=OntologyElementStatus.APPROVED,
            )
        ],
        constraints=[
            OntologyConstraint(
                id="con_rule",
                constraint_type=OntologyConstraintType.BUSINESS_RULE,
                expression="Call the care manager when an ER event is inside 14 days",
                related_class_id="cls_events",
                status=OntologyElementStatus.APPROVED,
            )
        ],
    )
    lines = approved_contract_lines(version)
    assert any(line.startswith("Rule: Call the care manager") for line in lines)
    assert any(line == "Alias: P1 means priority" for line in lines)
    rules = approved_rules_for_discovery(version)
    assert rules[0]["expression"].startswith("Call the care manager")
    assert rules[0]["related_entity"] == "CareEvents"
    assert approved_contract_lines(
        OntologyVersion(id="ver_draft", project_id="proj_1", version_label="draft", is_draft=True)
    ) == []


def test_session_note_is_kept_on_the_session_and_a_rule_stays_queued():
    recorded = agent_memory_service.record_exchange(
        fabric_id="fabric_context_classify",
        query="Should we outreach Lisa?",
        answer="No.",
    )
    noted = agent_memory_service.submit_feedback(
        fabric_id="fabric_context_classify",
        episode_id=recorded["episode_id"],
        session_id=recorded["session_id"],
        rating="down",
        correction_text="Only for this conversation, skip the call.",
    )
    assert noted["destination"] == "session"
    assert noted["enrichment_candidate_id"] is None
    context = agent_memory_service.build_query_context("fabric_context_classify", noted["session_id"])
    assert "Note: Only for this conversation" in context

    queued = agent_memory_service.submit_feedback(
        fabric_id="fabric_context_classify",
        episode_id=recorded["episode_id"],
        session_id=recorded["session_id"],
        rating="down",
        correction_text="Call the care manager when an ER event is inside 14 days",
        scope="ontology_constraint",
    )
    assert queued["destination"] == "ontology_constraint"
    assert queued["status"] == "queued"
