"""Tests for enterprise platform phases 1–4."""
import uuid

import pytest

from app.db.session import init_db
from app.models.ontology import (
    OntologyClass,
    OntologyElementStatus,
    OntologyRelationship,
    OntologyVersion,
)
from app.services.graph.graph_materialization_service import graph_materialization_service
from app.services.graph.graph_store import graph_store
from app.services.ontology.ontology_db_repository import ontology_db_repository
from app.services.ontology.schema_analyzer import schema_analyzer
from app.services.platform.fabric_store import fabric_store
from app.services.platform.job_service import job_service
from app.services.retrieval.retrieval_orchestrator import retrieval_orchestrator


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    from app.core import config

    config.settings.DATABASE_URL = f"sqlite:///{tmp_path / 'test.db'}"
    init_db()
    fabric_store._initialized = False
    fabric_store.initialize()


def test_fabric_store_roundtrip():
    fid = f"fabric_test_{uuid.uuid4().hex[:8]}"
    fabric_store.save({"id": fid, "name": "Test Fabric", "source_type": "database", "tags": []})
    loaded = fabric_store.get(fid)
    assert loaded is not None
    assert loaded["name"] == "Test Fabric"


def test_job_enqueue_and_get():
    job_id = job_service.enqueue("graph_build", "fabric_x", {"ontology_version_id": "ver_1"})
    job = job_service.get(job_id)
    assert job is not None
    assert job["status"] == "queued"


def test_schema_analyzer_rules():
    profile = {
        "tables": [{
            "name": "MemberDim",
            "columns": [{"name": "member_id", "type": "string"}, {"name": "plan_id", "type": "string"}],
            "sample_rows": [],
        }]
    }
    result = schema_analyzer.analyze(profile)
    assert len(result["entities"]) >= 1
    assert any(a["name"] == "member_id" for a in result["attributes"])


def test_graph_materialization_from_ontology():
    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    version_id = f"ver_{uuid.uuid4().hex[:8]}"
    fabric_id = f"fabric_{uuid.uuid4().hex[:8]}"
    cls_a = OntologyClass(
        id="cls_a", name="Member", normalized_name="Member", confidence_score=0.9,
        status=OntologyElementStatus.APPROVED,
    )
    cls_b = OntologyClass(
        id="cls_b", name="Claim", normalized_name="Claim", confidence_score=0.9,
        status=OntologyElementStatus.APPROVED,
    )
    rel = OntologyRelationship(
        id="rel_1",
        source_class_id="cls_a",
        target_class_id="cls_b",
        relationship_name="has_claim",
        confidence_score=0.8,
        status=OntologyElementStatus.APPROVED,
    )
    version = OntologyVersion(
        id=version_id,
        project_id=project_id,
        version_label="1.0",
        is_draft=False,
        classes=[cls_a, cls_b],
        relationships=[rel],
    )
    ontology_db_repository.save_version(version)
    fabric_store.save({"id": fabric_id, "name": "KG Test", "source_type": "database", "tags": []})

    result = graph_materialization_service.materialize(fabric_id, version_id, "postgres")
    assert result["node_count"] == 2
    assert result["edge_count"] == 1

    payload = graph_store.get_graph_payload(fabric_id, version_id)
    assert payload["node_count"] == 2


def test_retrieval_orchestrator_vector_only():
    fabric_id = f"fabric_{uuid.uuid4().hex[:8]}"
    fabric_store.save({"id": fabric_id, "name": "Retrieve Test", "source_type": "database", "tags": []})
    result = retrieval_orchestrator.retrieve(fabric_id, "test query", use_graph=False)
    assert result["fabric_id"] == fabric_id
    assert "chunks" in result
    assert result["graph_retrieval_enabled"] is False
