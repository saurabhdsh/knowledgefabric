"""Persist and load ontology projects, versions, and discovery runs."""
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.models.ontology import (
    OntologyProject,
    OntologyVersion,
    DiscoveryRun,
    DiscoveryRunStatus,
    SourceArtifact,
    OntologyChangeCandidate,
    GovernanceMode,
    OntologyVersionRecord,
    RecommendationType,
    PolicyDecisionLog,
    OntologyAuditLog,
)


class OntologyPersistenceService:
    """File-based persistence for ontology data (extensible to DB later)."""

    def __init__(self):
        self.data_dir = settings.ONTOLOGY_DATA_DIR
        self.projects_file = os.path.join(self.data_dir, "projects.json")
        self.versions_dir = os.path.join(self.data_dir, "versions")
        self.runs_file = os.path.join(self.data_dir, "runs.json")
        self.enrichment_dir = os.path.join(self.data_dir, "enrichment")
        self.candidates_file = os.path.join(self.enrichment_dir, "candidates.json")
        self.policy_logs_file = os.path.join(self.enrichment_dir, "policy_logs.json")
        self.audit_logs_file = os.path.join(self.enrichment_dir, "audit_logs.json")
        self.version_history_file = os.path.join(self.enrichment_dir, "ontology_versions.json")
        self.settings_file = os.path.join(self.enrichment_dir, "settings.json")
        self.snapshot_file = os.path.join(self.enrichment_dir, "ontology_snapshot.json")
        self.dataset_schemas_file = os.path.join(self.enrichment_dir, "dataset_schemas.json")
        os.makedirs(self.versions_dir, exist_ok=True)
        os.makedirs(self.enrichment_dir, exist_ok=True)

    def _load_json(self, path: str, default: Any = None) -> Any:
        if default is None:
            default = []
        if not os.path.exists(path):
            return default if default is not None else {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def _save_json(self, path: str, data: Any) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    # --- Projects ---

    def create_project(self, name: str, description: Optional[str] = None, domain: Optional[str] = None) -> OntologyProject:
        projects = self._load_json(self.projects_file, [])
        proj = OntologyProject(
            id=f"proj_{uuid.uuid4().hex[:12]}",
            name=name,
            description=description,
            domain=domain,
            source_artifacts=[],
            version_ids=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        projects.append(proj.model_dump())
        self._save_json(self.projects_file, projects)
        return proj

    def get_project(self, project_id: str) -> Optional[OntologyProject]:
        projects = self._load_json(self.projects_file, [])
        for p in projects:
            if p.get("id") == project_id:
                return OntologyProject(**p)
        return None

    def list_projects(self) -> List[OntologyProject]:
        projects = self._load_json(self.projects_file, [])
        return [OntologyProject(**p) for p in projects]

    def add_artifacts_to_project(self, project_id: str, artifacts: List[SourceArtifact]) -> bool:
        projects = self._load_json(self.projects_file, [])
        for p in projects:
            if p.get("id") == project_id:
                existing = p.get("source_artifacts", [])
                for a in artifacts:
                    existing.append(a.model_dump() if hasattr(a, "model_dump") else a)
                p["source_artifacts"] = existing
                p["updated_at"] = datetime.utcnow().isoformat()
                self._save_json(self.projects_file, projects)
                return True
        return False

    def delete_project(self, project_id: str) -> bool:
        """Remove project from storage. Optionally remove its version files and runs."""
        projects = self._load_json(self.projects_file, [])
        new_projects = [p for p in projects if p.get("id") != project_id]
        if len(new_projects) == len(projects):
            return False
        self._save_json(self.projects_file, new_projects)
        for fname in os.listdir(self.versions_dir):
            if fname.endswith(".json"):
                path = os.path.join(self.versions_dir, fname)
                try:
                    data = self._load_json(path, {})
                    if data.get("project_id") == project_id:
                        os.remove(path)
                except Exception:
                    pass
        runs = self._load_json(self.runs_file, [])
        new_runs = [r for r in runs if r.get("project_id") != project_id]
        if len(new_runs) != len(runs):
            self._save_json(self.runs_file, new_runs)
        return True

    # --- Versions ---

    def save_version(self, version: OntologyVersion) -> str:
        path = os.path.join(self.versions_dir, f"{version.id}.json")
        data = version.model_dump()
        self._save_json(path, data)
        return version.id

    def get_version(self, version_id: str) -> Optional[OntologyVersion]:
        path = os.path.join(self.versions_dir, f"{version_id}.json")
        if not os.path.exists(path):
            return None
        data = self._load_json(path, {})
        if not data:
            return None
        return OntologyVersion(**data)

    def list_versions_for_project(self, project_id: str) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for fname in os.listdir(self.versions_dir):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(self.versions_dir, fname)
            data = self._load_json(path, {})
            if data.get("project_id") == project_id:
                result.append({
                    "id": data.get("id"),
                    "version_label": data.get("version_label"),
                    "is_draft": data.get("is_draft", True),
                    "created_at": data.get("created_at"),
                })
        return result

    # --- Runs ---

    def create_run(self, project_id: str, artifact_ids: List[str]) -> DiscoveryRun:
        runs = self._load_json(self.runs_file, [])
        run = DiscoveryRun(
            id=f"run_{uuid.uuid4().hex[:12]}",
            project_id=project_id,
            status=DiscoveryRunStatus.QUEUED,
            artifact_ids=artifact_ids,
            run_logs=[],
            created_at=datetime.utcnow(),
        )
        runs.append(run.model_dump())
        self._save_json(self.runs_file, runs)
        return run

    def get_run(self, run_id: str) -> Optional[DiscoveryRun]:
        runs = self._load_json(self.runs_file, [])
        for r in runs:
            if r.get("id") == run_id:
                return DiscoveryRun(**r)
        return None

    def list_runs_for_project(self, project_id: str) -> List[Dict[str, Any]]:
        """List all discovery runs for a project (history), newest first."""
        runs = self._load_json(self.runs_file, [])
        project_runs = [r for r in runs if r.get("project_id") == project_id]
        project_runs.sort(key=lambda x: (x.get("created_at") or x.get("completed_at") or ""), reverse=True)
        return project_runs

    def update_run(
        self,
        run_id: str,
        status: Optional[DiscoveryRunStatus] = None,
        current_stage: Optional[str] = None,
        progress_percent: Optional[float] = None,
        result_version_id: Optional[str] = None,
        error_message: Optional[str] = None,
        log_entry: Optional[Dict[str, Any]] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> bool:
        runs = self._load_json(self.runs_file, [])
        for r in runs:
            if r.get("id") == run_id:
                if status is not None:
                    r["status"] = status.value if hasattr(status, "value") else status
                if current_stage is not None:
                    r["current_stage"] = current_stage
                if progress_percent is not None:
                    r["progress_percent"] = progress_percent
                if result_version_id is not None:
                    r["result_version_id"] = result_version_id
                if error_message is not None:
                    r["error_message"] = error_message
                if log_entry is not None:
                    r.setdefault("run_logs", []).append(log_entry)
                if started_at is not None:
                    r["started_at"] = started_at.isoformat() if hasattr(started_at, "isoformat") else str(started_at)
                if completed_at is not None:
                    r["completed_at"] = completed_at.isoformat() if hasattr(completed_at, "isoformat") else str(completed_at)
                r["updated_at"] = datetime.utcnow().isoformat()
                self._save_json(self.runs_file, runs)
                return True
        return False

    # --- Enrichment candidates / governance / versioning ---

    def get_governance_mode(self) -> GovernanceMode:
        data = self._load_json(self.settings_file, {})
        mode = data.get("governance_mode", GovernanceMode.ASSISTED.value)
        try:
            return GovernanceMode(mode)
        except Exception:
            return GovernanceMode.ASSISTED

    def set_governance_mode(self, mode: GovernanceMode, updated_by: str = "admin") -> Dict[str, Any]:
        prev = self._load_json(self.settings_file, {})
        data = {
            "governance_mode": mode.value if hasattr(mode, "value") else str(mode),
            "updated_by": updated_by,
            "updated_at": datetime.utcnow().isoformat(),
        }
        self._save_json(self.settings_file, data)
        self.save_audit_log(
            user=updated_by,
            action="governance_mode_changed",
            before_state=prev,
            after_state=data,
            rationale="Ontology governance mode updated.",
        )
        return data

    def save_candidates(self, candidates: List[OntologyChangeCandidate]) -> None:
        existing = self._load_json(self.candidates_file, [])
        by_id = {c.get("id"): c for c in existing}
        for c in candidates:
            payload = c.model_dump() if hasattr(c, "model_dump") else c
            by_id[payload.get("id")] = payload
        self._save_json(self.candidates_file, list(by_id.values()))

    def list_candidates(self) -> List[OntologyChangeCandidate]:
        data = self._load_json(self.candidates_file, [])
        out: List[OntologyChangeCandidate] = []
        for row in data:
            try:
                out.append(OntologyChangeCandidate(**row))
            except Exception:
                continue
        out.sort(key=lambda x: (x.createdAt or datetime.utcnow()), reverse=True)
        return out

    def get_candidate(self, candidate_id: str) -> Optional[OntologyChangeCandidate]:
        for c in self.list_candidates():
            if c.id == candidate_id:
                return c
        return None

    def update_candidate_status(
        self,
        candidate_id: str,
        status: str,
        reviewer: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[OntologyChangeCandidate]:
        candidates = self._load_json(self.candidates_file, [])
        updated = None
        for c in candidates:
            if c.get("id") == candidate_id:
                before = dict(c)
                c["status"] = status
                c["updatedAt"] = datetime.utcnow().isoformat()
                if reviewer:
                    c["reviewedBy"] = reviewer
                    c["reviewedAt"] = datetime.utcnow().isoformat()
                if notes:
                    c.setdefault("evidence", {})
                    c["evidence"]["review_notes"] = notes
                updated = c
                self.save_audit_log(
                    user=reviewer or "steward",
                    action=f"candidate_status_{status}",
                    before_state=before,
                    after_state=c,
                    rationale=notes or f"Candidate moved to {status}",
                )
                break
        if updated:
            self._save_json(self.candidates_file, candidates)
            return OntologyChangeCandidate(**updated)
        return None

    def save_policy_decision(self, candidate_id: str, policy_rule: str, decision: RecommendationType, reason: str) -> PolicyDecisionLog:
        logs = self._load_json(self.policy_logs_file, [])
        log = PolicyDecisionLog(
            id=f"plog_{uuid.uuid4().hex[:12]}",
            candidateId=candidate_id,
            policyRule=policy_rule,
            decision=decision,
            reason=reason,
            timestamp=datetime.utcnow(),
        )
        logs.append(log.model_dump())
        self._save_json(self.policy_logs_file, logs)
        return log

    def list_policy_decisions(self, candidate_id: Optional[str] = None) -> List[PolicyDecisionLog]:
        rows = self._load_json(self.policy_logs_file, [])
        out = []
        for r in rows:
            if candidate_id and r.get("candidateId") != candidate_id:
                continue
            try:
                out.append(PolicyDecisionLog(**r))
            except Exception:
                continue
        return out

    def save_audit_log(
        self,
        user: str,
        action: str,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any],
        rationale: Optional[str] = None,
    ) -> OntologyAuditLog:
        rows = self._load_json(self.audit_logs_file, [])
        item = OntologyAuditLog(
            id=f"audit_{uuid.uuid4().hex[:12]}",
            user=user,
            timestamp=datetime.utcnow(),
            action=action,
            beforeState=before_state,
            afterState=after_state,
            rationale=rationale,
        )
        rows.append(item.model_dump())
        self._save_json(self.audit_logs_file, rows)
        return item

    def list_audit_logs(self) -> List[OntologyAuditLog]:
        rows = self._load_json(self.audit_logs_file, [])
        out = []
        for r in rows:
            try:
                out.append(OntologyAuditLog(**r))
            except Exception:
                continue
        out.sort(key=lambda x: (x.timestamp or datetime.utcnow()), reverse=True)
        return out

    def get_current_ontology_snapshot(self) -> Dict[str, Any]:
        data = self._load_json(self.snapshot_file, {})
        if data:
            return data
        # Build minimal backward-compatible snapshot from newest ontology version files.
        attributes = []
        entities = []
        relationships = []
        for proj in self.list_projects():
            versions = self.list_versions_for_project(proj.id)
            if not versions:
                continue
            versions_sorted = sorted(versions, key=lambda v: str(v.get("created_at", "")), reverse=True)
            version = self.get_version(versions_sorted[0].get("id", ""))
            if not version:
                continue
            for c in version.classes:
                entities.append({"id": c.id, "name": c.normalized_name, "class_name": c.normalized_name})
            for a in version.attributes:
                class_name = next((c.normalized_name for c in version.classes if c.id == a.class_id), "Unknown")
                attributes.append({"id": a.id, "name": a.attribute_name, "entity": class_name, "class_name": class_name})
            for r in version.relationships:
                relationships.append({"id": r.id, "name": r.relationship_name, "source": r.source_class_id, "target": r.target_class_id})
        data = {"entities": entities, "attributes": attributes, "relationships": relationships, "updated_at": datetime.utcnow().isoformat()}
        self._save_json(self.snapshot_file, data)
        return data

    def upsert_ontology_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        snapshot["updated_at"] = datetime.utcnow().isoformat()
        self._save_json(self.snapshot_file, snapshot)
        return snapshot

    def create_version_record(
        self,
        change_ids: List[str],
        summary: str,
        approved_by: Optional[str],
        environment: str = "draft",
        rollback_reference: Optional[str] = None,
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> OntologyVersionRecord:
        existing = self._load_json(self.version_history_file, [])
        next_version = len(existing) + 1
        record = OntologyVersionRecord(
            id=f"ovr_{uuid.uuid4().hex[:12]}",
            versionNumber=f"v{next_version}",
            environment=environment,
            changeSummary=summary,
            changeIds=change_ids,
            approvedBy=approved_by,
            createdAt=datetime.utcnow(),
            rollbackReference=rollback_reference,
            snapshot=snapshot or self.get_current_ontology_snapshot(),
        )
        existing.append(record.model_dump())
        self._save_json(self.version_history_file, existing)
        return record

    def ensure_timeline_baseline_if_empty(self) -> None:
        """Create a single baseline version record when history is empty but a snapshot exists.

        Lets compare / rollback work without requiring a prior Promote action.
        """
        rows = self._load_json(self.version_history_file, [])
        if rows:
            return
        snap = self.get_current_ontology_snapshot()
        entities = snap.get("entities") or []
        attrs = snap.get("attributes") or []
        rels = snap.get("relationships") or []
        if not entities and not attrs and not rels:
            return
        self.create_version_record(
            change_ids=[],
            summary="Baseline snapshot (ontology workspace)",
            approved_by="system",
            environment="draft",
            snapshot=snap,
        )

    def list_version_records(self) -> List[OntologyVersionRecord]:
        rows = self._load_json(self.version_history_file, [])
        out = []
        for r in rows:
            try:
                out.append(OntologyVersionRecord(**r))
            except Exception:
                continue
        out.sort(key=lambda x: (x.createdAt or datetime.utcnow()), reverse=True)
        return out

    def get_version_record(self, version_id: str) -> Optional[OntologyVersionRecord]:
        for v in self.list_version_records():
            if v.id == version_id:
                return v
        return None

    def get_dataset_schema(self, source_dataset_id: str) -> Dict[str, Any]:
        all_schemas = self._load_json(self.dataset_schemas_file, {})
        return all_schemas.get(source_dataset_id, {})

    def save_dataset_schema(self, source_dataset_id: str, fields: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        all_schemas = self._load_json(self.dataset_schemas_file, {})
        payload = {
            "source_dataset_id": source_dataset_id,
            "fields": fields,
            "metadata": metadata or {},
            "updated_at": datetime.utcnow().isoformat(),
        }
        all_schemas[source_dataset_id] = payload
        self._save_json(self.dataset_schemas_file, all_schemas)
        return payload
