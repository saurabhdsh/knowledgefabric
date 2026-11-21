"""Phase 2 — evidence ontology, instance persistence, domain packs."""
from __future__ import annotations

import uuid

import pytest

from app.db.session import init_db
from app.models.ontology import (
    OntologyClass,
    OntologyElementStatus,
    OntologyEvidence,
    OntologyRelationship,
    OntologyVersion,
)
from app.services.domain_packs import (
    cost_of_care_collections,
    detect_primary_pack,
    infer_collections_from_packs,
    short_instance_label_from_packs,
)
from app.services.graph.graph_materialization_service import graph_materialization_service
from app.services.graph.graph_store import graph_store
from app.services.ontology.ontology_assembler import OntologyAssembler
from app.services.ontology.ontology_db_repository import ontology_db_repository
from app.services.ontology.relation_inference_engine import RelationInferenceEngine
from app.services.ontology.schema_analyzer import schema_analyzer
from app.services.platform.fabric_store import fabric_store


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'phase2.db'}")
    from app.core import config

    config.settings.DATABASE_URL = f"sqlite:///{tmp_path / 'phase2.db'}"
    config.settings.INSTANCE_GRAPH_ENABLED = False  # unit tests without table store
    init_db()
    fabric_store._initialized = False
    fabric_store.initialize()


def _profiled_schema():
    return {
        "source": "data_profile",
        "tables": [
            {
                "name": "members",
                "kind": "dimension",
                "row_count": 520,
                "primary_key": ["member_id"],
                "foreign_keys": [],
                "columns": [
                    {"name": "member_id", "type": "string", "required": True},
                    {"name": "member_name", "type": "string", "required": True},
                    {"name": "plan_id", "type": "string", "required": False},
                ],
            },
            {
                "name": "claims",
                "kind": "fact",
                "row_count": 1000,
                "primary_key": ["claim_id"],
                "foreign_keys": [
                    {
                        "column": "member_id",
                        "references_table": "members",
                        "references_column": "member_id",
                        "cardinality": "many-to-one",
                        "confidence": 1.0,
                        "overlap": 1.0,
                        "evidence": "value-inclusion+name",
                        "matched_values": 500,
                        "orphan_values": 0,
                    }
                ],
                "columns": [
                    {"name": "claim_id", "type": "string", "required": True},
                    {"name": "member_id", "type": "string", "required": True},
                    {"name": "paid_amount", "type": "number", "required": False},
                ],
            },
        ],
    }


def test_schema_analyzer_preserves_fk_evidence_and_confidence():
    result = schema_analyzer.analyze(_profiled_schema())
    assert len(result["entities"]) == 2
    rels = result["relationships"]
    assert len(rels) == 1
    rel = rels[0]
    assert rel["confidence"] == 1.0
    assert rel["cardinality"] == "n:1"
    assert rel["source_columns"] == ["member_id"]
    assert rel["target_columns"] == ["member_id"]
    assert "100%" in (rel.get("evidence_snippet") or rel["evidence"]["detail"])
    assert rel["evidence"]["basis"] == "value-inclusion+name"


def test_bind_tabular_preserves_cardinality_and_evidence():
    analyzed = schema_analyzer.analyze(_profiled_schema())
    entities = analyzed["entities"]
    candidates = [
        {
            **r,
            "relationship_name": r["name"],
            "source_entity_normalized": r["source_entity"],
            "target_entity_normalized": r["target_entity"],
            "tabular_binding": True,
        }
        for r in analyzed["relationships"]
    ]
    bound = RelationInferenceEngine().bind_tabular_relationship_candidates(entities, candidates)
    assert len(bound) == 1
    b = bound[0]
    assert b["cardinality_if_detected"] == "n:1"
    assert b["source_columns"] == ["member_id"]
    assert "100%" in b["evidence_snippet"]
    assert b["tabular_binding"]["basis"] == "value-inclusion+name"


def test_assembler_attaches_profile_evidence():
    entities = [
        {"id": "ent_a", "name": "claims", "normalized_name": "Claims", "confidence": 0.95},
        {"id": "ent_b", "name": "members", "normalized_name": "Members", "confidence": 0.95},
    ]
    relationships = [{
        "id": "rel_1",
        "source_class_id": "ent_a",
        "target_class_id": "ent_b",
        "relationship_name": "references_members",
        "confidence": 1.0,
        "cardinality_if_detected": "n:1",
        "source_columns": ["member_id"],
        "target_columns": ["member_id"],
        "evidence_snippet": "100% of claims.member_id exist in members.member_id",
        "artifact_type": "profile",
        "tabular_binding": {"basis": "value-inclusion+name", "overlap": 1.0},
    }]
    assembled = OntologyAssembler().assemble(
        project_id="proj_x",
        version_label="draft",
        entities=entities,
        relationships=relationships,
        attributes=[],
        business_rules=[],
        evidence_pool=[],
    )
    rel = assembled["relationships"][0]
    assert rel["confidence_score"] == 1.0
    assert rel["cardinality_if_detected"] == "n:1"
    assert rel["source_columns"] == ["member_id"]
    assert len(rel["evidence"]) == 1
    assert "100%" in rel["evidence"][0]["text_snippet"]


def test_domain_pack_cost_of_care_detection_and_labels():
    cols = ["member_id", "member_name", "risk_tier", "primary_condition", "ytd_total_cost"]
    pack = detect_primary_pack(cols)
    assert pack is not None and pack.id == "healthcare_cost_of_care"
    colls = infer_collections_from_packs(cols, rows_imported=10)
    assert any(c["name"] == "members" for c in colls)
    assert "members" in cost_of_care_collections()
    label = short_instance_label_from_packs(
        "members",
        {"member_id": "MEM-1", "member_name": "Lisa Chen"},
        "MEM-1",
    )
    assert label == "Lisa Chen"


def test_domain_pack_itsm_detection():
    cols = ["incident_number", "short_description", "priority", "cmdb_ci_id"]
    pack = detect_primary_pack(cols)
    assert pack is not None and pack.id == "itsm_servicenow"
    colls = infer_collections_from_packs(cols)
    assert any(c["name"] == "incidents" for c in colls)


def test_graph_materialization_preserves_relationship_evidence():
    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    version_id = f"ver_{uuid.uuid4().hex[:8]}"
    fabric_id = f"fabric_{uuid.uuid4().hex[:8]}"
    cls_a = OntologyClass(
        id="cls_a", name="claims", normalized_name="Claims", confidence_score=0.95,
        status=OntologyElementStatus.APPROVED,
    )
    cls_b = OntologyClass(
        id="cls_b", name="members", normalized_name="Members", confidence_score=0.95,
        status=OntologyElementStatus.APPROVED,
    )
    rel = OntologyRelationship(
        id="rel_1",
        source_class_id="cls_a",
        target_class_id="cls_b",
        relationship_name="references_members",
        confidence_score=1.0,
        cardinality_if_detected="n:1",
        source_columns=["member_id"],
        target_columns=["member_id"],
        status=OntologyElementStatus.APPROVED,
        evidence=[
            OntologyEvidence(
                id="evt_1",
                artifact_id="profile:Claims->Members",
                artifact_type="profile",
                text_snippet="100% of claims.member_id exist in members.member_id (value-inclusion+name)",
                extraction_stage="schema_analyzer",
            )
        ],
        tabular_binding={"basis": "value-inclusion+name", "overlap": 1.0},
    )
    ontology_db_repository.ensure_project(project_id, name="P2", fabric_id=fabric_id)
    ontology_db_repository.save_version(
        OntologyVersion(
            id=version_id,
            project_id=project_id,
            version_label="v1",
            is_draft=False,
            classes=[cls_a, cls_b],
            relationships=[rel],
            attributes=[],
            constraints=[],
        )
    )
    fabric_store.save({"id": fabric_id, "name": "P2 Fabric", "source_type": "database", "tags": []})
    result = graph_materialization_service.materialize(fabric_id, version_id)
    assert result["class_node_count"] == 2
    payload = graph_store.get_graph_payload(fabric_id, version_id)
    assert payload["edge_count"] == 1
    edge = payload["edges"][0]
    assert edge["confidence"] == 1.0
    assert edge["evidence_refs"]
    assert "100%" in (edge["evidence_refs"][0].get("snippet") or "")
