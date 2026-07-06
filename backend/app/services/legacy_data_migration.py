"""Assign pre-auth fabrics and ontology projects to the primary admin user."""
from __future__ import annotations

import logging

from app.db.models import FabricRecord, OntologyProjectRecord
from app.db.session import db_session
from app.services.auth_service import PRIMARY_ADMIN_USERNAME, auth_service
from app.services.ontology.ontology_access import register_project_owner
from app.services.ontology.ontology_persistence_service import OntologyPersistenceService

logger = logging.getLogger(__name__)


def migrate_legacy_data_to_primary_admin() -> None:
    """Claim unowned platform data for the seed admin (Saurabh)."""
    admin = auth_service.get_user_by_username(PRIMARY_ADMIN_USERNAME)
    if not admin:
        logger.warning("Primary admin %s not found; skipping legacy data migration", PRIMARY_ADMIN_USERNAME)
        return

    fabric_count = 0
    db_project_count = 0
    file_project_count = 0

    with db_session() as session:
        fabric_count = (
            session.query(FabricRecord)
            .filter(FabricRecord.owner_id.is_(None))
            .update({FabricRecord.owner_id: admin.id}, synchronize_session=False)
        )
        db_project_count = (
            session.query(OntologyProjectRecord)
            .filter(OntologyProjectRecord.owner_id.is_(None))
            .update({OntologyProjectRecord.owner_id: admin.id}, synchronize_session=False)
        )

    persistence = OntologyPersistenceService()
    for proj in persistence.list_projects():
        with db_session() as session:
            rec = session.get(OntologyProjectRecord, proj.id)
            if rec is None or rec.owner_id is None:
                register_project_owner(proj.id, proj.name, owner_id=admin.id)
                file_project_count += 1

    if fabric_count or db_project_count or file_project_count:
        logger.info(
            "Legacy data migrated to %s (%s): %d fabrics, %d db ontology projects, %d file ontology projects",
            PRIMARY_ADMIN_USERNAME,
            admin.id,
            fabric_count,
            db_project_count,
            file_project_count,
        )
