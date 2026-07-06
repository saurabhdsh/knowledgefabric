from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.api.v1.endpoints import ontology as ontology_endpoints
from app.models.ontology import (
    OntologyAttribute,
    OntologyClass,
    OntologyRelationship,
    OntologyVersion,
    OntologyElementStatus,
)


client = TestClient(app)


def _create_test_project_and_version() -> tuple[str, str]:
    project = ontology_endpoints.persistence.create_project(
        name=f"agent-utils-test-{datetime.utcnow().timestamp()}",
        description="Wave 1.5 api tests",
        domain="testing",
    )
    version = OntologyVersion(
        id=f"ver_test_{int(datetime.utcnow().timestamp() * 1000)}",
        project_id=project.id,
        version_label="test-v1",
        is_draft=True,
        classes=[
            OntologyClass(
                id="cls_patient",
                name="Patient",
                normalized_name="Patient",
                definition="Person receiving healthcare services",
                confidence_score=0.95,
                status=OntologyElementStatus.APPROVED,
                source_evidence=[],
            ),
        ],
        relationships=[
            OntologyRelationship(
                id="rel_patient_visit",
                source_class_id="cls_patient",
                relationship_name="has_visit",
                target_class_id="cls_visit",
                confidence_score=0.8,
                status=OntologyElementStatus.APPROVED,
                evidence=[],
            ),
        ],
        attributes=[
            OntologyAttribute(
                id="attr_patient_id",
                class_id="cls_patient",
                attribute_name="patient_id",
                normalized_name="patient_id",
                data_type_guess="string",
                confidence_score=0.9,
                status=OntologyElementStatus.APPROVED,
                evidence=[],
            ),
        ],
        constraints=[],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    ontology_endpoints.persistence.save_version(version)
    return project.id, version.id


def test_agent_query_and_trust_score_endpoints():
    project_id, version_id = _create_test_project_and_version()

    query_res = client.post(
        "/api/v1/ontology/agent/query",
        json={
            "project_id": project_id,
            "version_id": version_id,
            "query": "patient id",
            "top_k": 5,
            "role": "agent_developer",
            "include_debug": True,
        },
    )
    assert query_res.status_code == 200
    body = query_res.json()
    assert body["success"] is True
    assert "results" in body["data"]
    assert len(body["data"]["results"]) >= 1
    assert "trust_score" in body["data"]
    assert "query_tokens" in body["data"]["debug"]

    trust_res = client.get(f"/api/v1/ontology/agent/trust-score/{project_id}/{version_id}")
    assert trust_res.status_code == 200
    trust_data = trust_res.json()["data"]
    assert "overall_score" in trust_data
    assert "type_diagnostics" in trust_data
    assert isinstance(trust_data["type_diagnostics"], list)


def test_agent_contract_validation_and_upsert():
    bad = client.post(
        "/api/v1/ontology/agent/contracts",
        json={
            "contract_id": "contract_bad",
            "name": "Bad Contract",
            "version": "1.0",
            "description": "invalid semver",
            "input_schema": {},
            "output_schema": {},
            "compatibility": "backward_compatible",
            "owner": "qa",
            "tags": ["test"],
        },
    )
    assert bad.status_code == 422

    ok = client.post(
        "/api/v1/ontology/agent/contracts",
        json={
            "contract_id": "contract_good",
            "name": "Good Contract",
            "version": "1.0.0",
            "description": "valid semver",
            "input_schema": {"query": "string"},
            "output_schema": {"answer": "string"},
            "compatibility": "backward_compatible",
            "owner": "qa",
            "tags": ["test"],
        },
    )
    assert ok.status_code == 200
    list_res = client.get("/api/v1/ontology/agent/contracts")
    assert list_res.status_code == 200
    assert any(c["contract_id"] == "contract_good" for c in list_res.json()["data"])

    del_res = client.post(
        "/api/v1/ontology/agent/contracts/delete",
        json={"contract_id": "contract_good", "version": "1.0.0"},
    )
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True
    after = client.get("/api/v1/ontology/agent/contracts")
    assert not any(c["contract_id"] == "contract_good" for c in after.json()["data"])

    missing = client.post(
        "/api/v1/ontology/agent/contracts/delete",
        json={"contract_id": "contract_good", "version": "1.0.0"},
    )
    assert missing.status_code == 404


def test_agent_policy_evaluate_masks_and_denies_by_purpose():
    res = client.post(
        "/api/v1/ontology/agent/policy/evaluate",
        json={
            "role": "agent_developer",
            "purpose": "analytics",
            "strict_mode": True,
            "payload": {
                "patient_id": "P123",
                "ssn": "123-45-6789",
                "clinical_summary": "stable",
            },
        },
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["allowed"] is False
    assert "patient_id" in data["masked_fields"]
    assert "ssn" in data["masked_fields"]
    assert "denied_reasons" in data
    assert len(data["denied_reasons"]) >= 1
