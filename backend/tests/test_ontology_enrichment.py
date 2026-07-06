import os
import tempfile

from app.models.ontology import GovernanceMode
from app.services.ontology.ontology_enrichment_service import OntologyEnrichmentService
from app.services.ontology.ontology_persistence_service import OntologyPersistenceService


def _tmp_persistence() -> OntologyPersistenceService:
    tmp = tempfile.mkdtemp()
    os.environ["ONTOLOGY_DATA_DIR"] = tmp
    svc = OntologyPersistenceService()
    svc.data_dir = tmp
    svc.projects_file = os.path.join(tmp, "projects.json")
    svc.versions_dir = os.path.join(tmp, "versions")
    svc.runs_file = os.path.join(tmp, "runs.json")
    svc.enrichment_dir = os.path.join(tmp, "enrichment")
    svc.candidates_file = os.path.join(svc.enrichment_dir, "candidates.json")
    svc.policy_logs_file = os.path.join(svc.enrichment_dir, "policy_logs.json")
    svc.audit_logs_file = os.path.join(svc.enrichment_dir, "audit_logs.json")
    svc.version_history_file = os.path.join(svc.enrichment_dir, "ontology_versions.json")
    svc.settings_file = os.path.join(svc.enrichment_dir, "settings.json")
    svc.snapshot_file = os.path.join(svc.enrichment_dir, "ontology_snapshot.json")
    os.makedirs(svc.versions_dir, exist_ok=True)
    os.makedirs(svc.enrichment_dir, exist_ok=True)
    return svc


def test_discovery_creates_candidates():
    persistence = _tmp_persistence()
    enrichment = OntologyEnrichmentService(persistence=persistence)
    persistence.set_governance_mode(GovernanceMode.ASSISTED, "tester")
    candidates = enrichment.discover_candidates(
        source_dataset_id="ds_1",
        fields=[
            {"name": "member_id", "type": "string", "sample_values": ["M1"]},
            {"name": "diagnosis_cluster", "type": "string", "sample_values": ["Cardio"]},
        ],
        created_by="tester",
    )
    assert len(candidates) == 2
    assert any(c.sensitivity.value in {"pii", "phi"} for c in candidates)


def test_controlled_auto_apply_policy():
    persistence = _tmp_persistence()
    enrichment = OntologyEnrichmentService(persistence=persistence)
    persistence.set_governance_mode(GovernanceMode.CONTROLLED_AUTO_APPLY, "tester")
    candidates = enrichment.discover_candidates(
        source_dataset_id="ds_2",
        fields=[{"name": "provider_group_name", "type": "string", "sample_values": ["A"]}],
        created_by="tester",
    )
    assert len(candidates) == 1
    assert candidates[0].status.value in {"pending_approval", "auto_applied"}


def test_timeline_baseline_creates_single_record():
    persistence = _tmp_persistence()
    persistence.upsert_ontology_snapshot(
        {
            "entities": [{"id": "e1", "name": "Patient"}],
            "attributes": [],
            "relationships": [],
        }
    )
    persistence.ensure_timeline_baseline_if_empty()
    versions = persistence.list_version_records()
    assert len(versions) == 1
    persistence.ensure_timeline_baseline_if_empty()
    assert len(persistence.list_version_records()) == 1


def test_candidate_status_and_versioning():
    persistence = _tmp_persistence()
    enrichment = OntologyEnrichmentService(persistence=persistence)
    candidates = enrichment.discover_candidates(
        source_dataset_id="ds_3",
        fields=[{"name": "care_gap_priority_score", "type": "number", "sample_values": [0.5]}],
        created_by="tester",
    )
    cid = candidates[0].id
    approved = persistence.update_candidate_status(cid, "approved", "reviewer", "ok")
    assert approved is not None
    version = persistence.create_version_record([cid], "test promote", "reviewer", "draft")
    assert version.id.startswith("ovr_")
    fetched = persistence.get_version_record(version.id)
    assert fetched is not None


def test_schema_drift_detection_generates_candidates():
    persistence = _tmp_persistence()
    enrichment = OntologyEnrichmentService(persistence=persistence)
    persistence.set_governance_mode(GovernanceMode.ASSISTED, "tester")

    enrichment.discover_candidates(
        source_dataset_id="ds_drift",
        fields=[
            {"name": "member_id", "type": "string"},
            {"name": "old_score", "type": "number"},
        ],
        created_by="tester",
    )

    second = enrichment.discover_candidates(
        source_dataset_id="ds_drift",
        fields=[
            {"name": "subscriber_id", "type": "string"},
            {"name": "old_score", "type": "string"},
        ],
        created_by="tester",
    )

    change_types = {c.changeType.value for c in second}
    assert "change_data_type" in change_types
    assert "rename_attribute" in change_types or "deprecate_attribute" in change_types
