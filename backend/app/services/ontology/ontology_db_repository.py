"""PostgreSQL-backed ontology persistence (dual-write with file store)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.db.models import OntologyAuditRecord, OntologyProjectRecord, OntologyVersionRecord
from app.db.session import db_session, get_session_factory
from app.models.ontology import OntologyElementStatus, OntologyVersion
from app.services.ontology.ontology_persistence_service import OntologyPersistenceService

logger = logging.getLogger(__name__)


class OntologyDbRepository:
    def __init__(self) -> None:
        self._file = OntologyPersistenceService()

    def ensure_project(
        self,
        project_id: str,
        name: str,
        fabric_id: Optional[str] = None,
        description: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> str:
        with db_session() as session:
            rec = session.get(OntologyProjectRecord, project_id)
            if rec is None:
                rec = OntologyProjectRecord(
                    id=project_id,
                    name=name,
                    description=description,
                    domain=domain,
                    fabric_id=fabric_id,
                )
                session.add(rec)
            else:
                rec.name = name
                if fabric_id:
                    rec.fabric_id = fabric_id
        if not self._file.get_project(project_id):
            self._file.create_project(name, description, domain)
        return project_id

    def create_discovery_run(self, project_id: str, config: Dict[str, Any]) -> str:
        run = self._file.create_run(project_id, config.get("artifact_ids") or [])
        return run.id

    def save_version(self, version: OntologyVersion) -> str:
        payload = version.model_dump(mode="json")
        with db_session() as session:
            rec = session.get(OntologyVersionRecord, version.id)
            if rec is None:
                rec = OntologyVersionRecord(id=version.id, project_id=version.project_id, payload={})
                session.add(rec)
            rec.version_label = version.version_label
            rec.is_draft = version.is_draft
            rec.is_approved = not version.is_draft and bool(version.approved_at)
            rec.approved_by = version.approved_by
            rec.approved_at = version.approved_at
            rec.payload = payload
            rec.updated_at = datetime.utcnow()
        self._file.save_version(version)
        return version.id

    def get_version(self, version_id: str) -> Optional[OntologyVersion]:
        session = get_session_factory()()
        try:
            rec = session.get(OntologyVersionRecord, version_id)
            if rec and rec.payload:
                return OntologyVersion(**rec.payload)
        finally:
            session.close()
        return self._file.get_version(version_id)

    def approve_version(
        self,
        version_id: str,
        approved_by: Optional[str] = None,
        require_all_approved: bool = False,
    ) -> OntologyVersion:
        version = self.get_version(version_id)
        if not version:
            raise ValueError("Version not found")

        for c in version.classes:
            if c.status != OntologyElementStatus.REJECTED:
                c.status = OntologyElementStatus.APPROVED
        for r in version.relationships:
            if r.status != OntologyElementStatus.REJECTED:
                r.status = OntologyElementStatus.APPROVED
        for a in version.attributes:
            if a.status != OntologyElementStatus.REJECTED:
                a.status = OntologyElementStatus.APPROVED

        version.is_draft = False
        version.approved_by = approved_by
        version.approved_at = datetime.utcnow()
        version.updated_at = datetime.utcnow()
        self.save_version(version)
        self._audit(version.project_id, version_id, "approve", approved_by, {})
        return version

    def _audit(
        self,
        project_id: str,
        version_id: str,
        action: str,
        actor: Optional[str],
        details: Dict[str, Any],
    ) -> None:
        with db_session() as session:
            session.add(
                OntologyAuditRecord(
                    id=f"aud_{uuid.uuid4().hex[:12]}",
                    project_id=project_id,
                    version_id=version_id,
                    action=action,
                    actor=actor,
                    details=details,
                )
            )


ontology_db_repository = OntologyDbRepository()
