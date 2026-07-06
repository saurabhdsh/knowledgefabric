from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_enrichment_discover_and_list_candidates():
    payload = {
        "source_dataset_id": "api_ds_1",
        "fields": [
            {"name": "member_id", "type": "string", "sample_values": ["M1", "M2"]},
            {"name": "provider_risk_tier", "type": "string", "sample_values": ["T1"]},
        ],
        "metadata": {"source": "api-test"},
        "created_by": "pytest",
    }
    res = client.post("/api/v1/ontology/enrichment/discover", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert len(body["data"]) >= 1

    res2 = client.get("/api/v1/ontology/enrichment/candidates")
    assert res2.status_code == 200
    assert res2.json()["success"] is True


def test_governance_mode_setting_api():
    res = client.put("/api/v1/ontology/settings/governance-mode", json={"mode": "assisted", "updated_by": "pytest"})
    assert res.status_code == 200
    out = client.get("/api/v1/ontology/settings/governance-mode")
    assert out.status_code == 200
    assert out.json()["data"]["mode"] in {"manual", "assisted", "controlled_auto_apply"}
