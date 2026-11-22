"""Document ontology: nothing is stated unless a sentence in the source states it."""
from __future__ import annotations

from app.services.ontology.attribute_mapper import AttributeMapper
from app.services.ontology.concept_extractor import ConceptExtractor
from app.services.ontology.llm_ontology_service import LLMOntologyService
from app.services.ontology.ontology_assembler import OntologyAssembler
from app.services.ontology.ontology_classifier import OntologyClassifier
from app.services.ontology.relation_inference_engine import RelationInferenceEngine
from app.services.ontology.text_match import find_mentions, mentions, quote_in_text

ENTITIES = [
    {"id": "member", "name": "Member", "normalized_name": "Member"},
    {"id": "provider", "name": "Provider", "normalized_name": "Provider"},
    {"id": "claim", "name": "Claim", "normalized_name": "Claim"},
    {"id": "plan", "name": "Plan", "normalized_name": "Plan"},
    {"id": "care_plan", "name": "Care Plan", "normalized_name": "Care Plan"},
]
NAMES = {e["name"].lower(): e["id"] for e in ENTITIES}


def _edges(rels):
    return {(r["source_class_id"], r["relationship_name"], r["target_class_id"]) for r in rels}


# --------------------------------------------------------------------------
# Whole-word matching
# --------------------------------------------------------------------------

def test_names_match_whole_words_only():
    assert mentions("Plan", "Each plan has a deductible.")
    assert mentions("Plan", "Plans renew every January.")
    assert mentions("Policy", "Two policies were issued.")
    # "plan" inside "explanation" and "claim" inside "disclaimer" are not mentions.
    assert not mentions("Plan", "An explanation of benefits is sent.")
    assert not mentions("Claim", "This disclaimer applies.")


def test_longer_name_wins_over_a_name_inside_it():
    found = find_mentions("The care plan is reviewed by the provider.", NAMES)
    assert [ident for _, _, ident in found] == ["care_plan", "provider"]


def test_quote_must_appear_word_for_word():
    text = "The provider submits a claim\nfor the member within 90 days."
    assert quote_in_text("the provider submits a claim for the member", text)
    assert not quote_in_text("the member submits a claim", text)
    assert not quote_in_text("a claim", text)  # too short to be evidence


# --------------------------------------------------------------------------
# Relationships
# --------------------------------------------------------------------------

def test_subject_and_object_follow_the_sentence():
    rels = RelationInferenceEngine().infer_relationships(
        ENTITIES,
        [{"name": "submits", "normalized_name": "Submits",
          "evidence_snippet": "The provider submits a claim for the member."}],
        [],
    )
    assert _edges(rels) == {("provider", "submits", "claim")}
    assert rels[0]["evidence"]["basis"] == "sentence_order"


def test_substring_does_not_create_a_relationship():
    engine = RelationInferenceEngine()
    rels = engine.infer_relationships(
        ENTITIES,
        [{"name": "requires", "normalized_name": "Requires",
          "evidence_snippet": "An explanation of benefits requires review by the provider."}],
        [],
    )
    # Only "provider" is named; "plan" is part of "explanation".
    assert rels == []
    assert engine.last_dropped and "names an entity on each side" in engine.last_dropped[0]["reason"]


def test_relationship_without_two_named_ends_is_dropped_not_guessed():
    engine = RelationInferenceEngine()
    rels = engine.infer_relationships(
        ENTITIES,
        [{"name": "escalates", "normalized_name": "Escalates",
          "evidence_snippet": "The supervisor escalates the case."}],
        [],
    )
    assert rels == []
    assembled = OntologyAssembler().assemble(
        project_id="p", version_label="draft", entities=ENTITIES,
        relationships=[{"relationship_name": "escalates", "source_class_id": None, "target_class_id": None}],
        attributes=[{"attribute_name": "priority", "normalized_name": "Priority"}],
        business_rules=[],
    )
    assert assembled["relationships"] == []
    assert assembled["attributes"] == []
    assert {d["kind"] for d in assembled["dropped"]} == {"relationship", "attribute"}


def test_passive_sentence_keeps_its_direction():
    extractor = ConceptExtractor()
    text = "A Claim is submitted by the Provider. A Claim is reviewed by the Plan."
    cands = extractor.extract_from_text(text)["relationships"]
    rels = RelationInferenceEngine().infer_relationships(ENTITIES, cands, [])
    assert ("claim", "submitted by", "provider") in _edges(rels)
    assert ("claim", "reviewed by", "plan") in _edges(rels)


def test_one_verb_in_two_sentences_gives_two_relationships():
    extractor = ConceptExtractor()
    text = "Each Member has a Plan. Every Provider has a Claim history."
    classified = OntologyClassifier().classify_candidates(extractor.extract_from_text(text), {})
    rels = RelationInferenceEngine().infer_relationships(ENTITIES, classified["relationships"], [])
    assert {("member", "has", "plan"), ("provider", "has", "claim")} <= _edges(rels)


def test_model_triple_is_kept_only_with_a_real_quote():
    chunks = [{"content": "The provider submits a claim for the member. Claims are paid by the plan."}]
    engine = RelationInferenceEngine()
    rels = engine.infer_relationships(
        ENTITIES,
        [
            {"subject": "Provider", "predicate": "submits", "object": "Claim",
             "quote": "The provider submits a claim for the member."},
            # Invented sentence: not in the source.
            {"subject": "Member", "predicate": "pays", "object": "Provider",
             "quote": "The member pays the provider directly."},
            # Real sentence, but it does not name the stated subject.
            {"subject": "Member", "predicate": "pays", "object": "Claim",
             "quote": "Claims are paid by the plan."},
        ],
        chunks,
    )
    assert _edges(rels) == {("provider", "submits", "claim")}
    assert rels[0]["confidence"] == 0.75
    reasons = " | ".join(d["reason"] for d in engine.last_dropped)
    assert "not in the source text" in reasons and "does not name both ends" in reasons


# --------------------------------------------------------------------------
# Model output is checked against the text
# --------------------------------------------------------------------------

def test_model_output_is_discarded_when_the_text_does_not_state_it():
    text = (
        "The provider submits a claim for the member. "
        "A claim must include a diagnosis code. "
        "An explanation of benefits is sent to the provider."
    )
    raw = {
        "entities": [
            {"name": "Provider"}, {"name": "Claim"}, {"name": "Member"},
            {"name": "Pharmacy"},  # not in the text
        ],
        "relationships": [
            {"subject": "Provider", "predicate": "submits", "object": "Claim",
             "quote": "The provider submits a claim for the member."},
            {"subject": "Provider", "predicate": "requires", "object": "Plan",
             "quote": "An explanation of benefits is sent to the provider."},
            {"subject": "Member", "predicate": "owns", "object": "Claim",
             "quote": "Members own their claims."},
        ],
        "attributes": [
            {"name": "diagnosis code", "entity": "Claim"},
            {"name": "tax id", "entity": "Provider"},
        ],
        "business_rules": [
            {"expression": "A claim must include a diagnosis code.", "entity": "Claim"},
            {"expression": "Claims must be filed within 30 days."},
        ],
    }
    out = LLMOntologyService()._normalize_llm_output(raw, text)
    assert {e["name"] for e in out["entities"]} == {"Provider", "Claim", "Member"}
    assert [(r["subject"], r["predicate"], r["object"]) for r in out["relationships"]] == [
        ("Provider", "submits", "Claim")
    ]
    assert [a["name"] for a in out["attributes"]] == ["diagnosis code"]
    assert [b["expression"] for b in out["business_rules"]] == ["A claim must include a diagnosis code."]
    assert out["discarded"] == {"entities": 1, "relationships": 2, "attributes": 1, "business_rules": 1}
    # Confidence reflects what was checked, not what the model said about itself.
    assert all(r["confidence"] == 0.75 and r["quote_verified"] for r in out["relationships"])


def test_same_verb_with_different_ends_stays_separate():
    llm = {
        "entities": [], "attributes": [], "business_rules": [],
        "relationships": [
            {"name": "submits", "normalized_name": "submits", "subject": "Provider", "object": "Claim",
             "confidence": 0.75, "evidence_snippet": "The provider submits a claim."},
            {"name": "submits", "normalized_name": "submits", "subject": "Member", "object": "Appeal",
             "confidence": 0.75, "evidence_snippet": "The member submits an appeal."},
        ],
    }
    out = OntologyClassifier().classify_candidates(
        {"entities": [], "relationships": [], "attributes": [], "business_rules": []}, llm
    )
    assert len(out["relationships"]) == 2


def test_repetition_boost_is_capped():
    items = [{"name": "Claim", "normalized_name": "Claim", "confidence": 0.5,
              "evidence_snippet": f"Sentence {i} about a claim."} for i in range(12)]
    out = OntologyClassifier().classify_candidates(
        {"entities": items, "relationships": [], "attributes": [], "business_rules": []}, {}
    )
    assert len(out["entities"]) == 1
    assert out["entities"][0]["confidence"] == 0.65


# --------------------------------------------------------------------------
# Attributes and entity candidates
# --------------------------------------------------------------------------

def test_attribute_without_a_named_entity_is_left_out():
    mapper = AttributeMapper()
    result = mapper.map_attributes_to_classes(
        [
            {"name": "status", "normalized_name": "Status",
             "evidence_snippet": "Claim status: paid, denied, pending"},
            {"name": "priority", "normalized_name": "Priority",
             "evidence_snippet": "Priority: high, medium, low"},
            {"name": "npi", "normalized_name": "Npi", "entity": "Providers", "evidence_snippet": ""},
        ],
        ENTITIES,
    )
    assert {(a["attribute_name"], a["class_id"]) for a in result} == {("status", "claim"), ("npi", "provider")}
    assert mapper.last_unassigned == ["priority"]


def test_sentence_openers_are_not_entities():
    text = (
        "We hope the Member reads this notice. If the Provider disagrees, the Provider may appeal. "
        "However, payment follows the Care Plan."
    )
    names = {e["normalized_name"] for e in ConceptExtractor().extract_from_text(text)["entities"]}
    assert {"Member", "Provider", "Care Plan"} <= names
    assert not names & {"We", "If", "However", "The Member", "The Provider"}
