"""Per-user access control for ontology projects."""
from __future__ import annotations

from typing import Optional, Set

from app.core.user_context import get_current_user_id
from app.db.models import OntologyProjectRecord
from app.db.session import db_session, get_session_factory


def register_project_owner(project_id: str, name: str, owner_id: Optional[str] = None) -> None:
    owner = owner_id or get_current_user_id()
    if not owner:
        return
    with db_session() as session:
        rec = session.get(OntologyProjectRecord, project_id)
        if rec is None:
            rec = OntologyProjectRecord(id=project_id, name=name, owner_id=owner)
            session.add(rec)
        else:
            rec.owner_id = owner


def user_owns_project(project_id: str) -> bool:
    owner = get_current_user_id()
    if not owner:
        return True
    session = get_session_factory()()
    try:
        rec = session.get(OntologyProjectRecord, project_id)
        if rec is None:
            return False
        return rec.owner_id == owner
    finally:
        session.close()


def allowed_project_ids() -> Optional[Set[str]]:
    owner = get_current_user_id()
    if not owner:
        return None
    session = get_session_factory()()
    try:
        rows = (
            session.query(OntologyProjectRecord.id)
            .filter(OntologyProjectRecord.owner_id == owner)
            .all()
        )
        return {row[0] for row in rows}
    finally:
        session.close()
