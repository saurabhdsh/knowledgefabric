"""Write an accepted alias or rule onto the fabric's ontology draft.

The approved version is left in place. Answers keep using it until a steward
approves the draft.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from app.models.ontology import (
    OntologyConstraint,
    OntologyConstraintType,
    OntologyElementStatus,
    OntologyEvidence,
)
from app.services.ontology.ontology_db_repository import ontology_db_repository
from app.services.ontology.ontology_persistence_service import OntologyPersistenceService


def _norm(value: str) -> str:
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


def draft_version_for_fabric(fabric: Dict[str, Any]):
    """Newest draft on the fabric's ontology project, or a draft cloned from the approved version."""
    project_id = fabric.get("ontology_project_id")
    if not project_id:
        return None
    persistence = OntologyPersistenceService()
    for meta in persistence.list_versions_for_project(project_id):
        version = ontology_db_repository.get_version(meta.get("id"))
        if version and version.is_draft:
            return version
    approved_id = fabric.get("approved_ontology_version_id")
    approved = ontology_db_repository.get_version(approved_id) if approved_id else None
    if not approved:
        return None
    cloned = approved.model_copy(deep=True)
    cloned.id = f"ver_{uuid.uuid4().hex[:12]}"
    cloned.is_draft = True
    cloned.version_label = "draft"
    cloned.approved_by = None
    cloned.approved_at = None
    cloned.created_at = datetime.utcnow()
    cloned.updated_at = datetime.utcnow()
    ontology_db_repository.save_version(cloned)
    return cloned


def apply_ontology_candidate(
    fabric: Dict[str, Any],
    classification: Dict[str, Any],
    proposed_fact: str,
    episode_id: Optional[str],
) -> Dict[str, Any]:
    version = draft_version_for_fabric(fabric)
    if version is None:
        raise ValueError("This fabric has no ontology draft to receive the correction.")
    destination = classification.get("destination")
    now = datetime.utcnow()
    evidence = [
        OntologyEvidence(
            id=f"evt_ctx_{uuid.uuid4().hex[:8]}",
            artifact_id=f"episode:{episode_id or 'none'}",
            artifact_type="context_episode",
            text_snippet=(proposed_fact or "")[:500],
            extraction_stage="context_layer",
        )
    ]
    element_id = None
    if destination == "ontology_alias":
        target = _norm(str(classification.get("attribute_name") or ""))
        alias = str(classification.get("alias") or "").strip()
        for attribute in version.attributes:
            if _norm(attribute.attribute_name) == target or _norm(attribute.normalized_name) == target:
                existing = list(attribute.aliases or [])
                if alias and alias not in existing:
                    existing.append(alias)
                attribute.aliases = existing
                attribute.updated_at = now
                element_id = attribute.id
                break
        if element_id is None:
            raise ValueError("The attribute for this alias is not on the ontology draft.")
    elif destination == "ontology_constraint":
        expression = (proposed_fact or "").strip()[:500]
        if any((c.expression or "").strip().lower() == expression.lower() for c in version.constraints):
            element_id = next(
                c.id for c in version.constraints if (c.expression or "").strip().lower() == expression.lower()
            )
        else:
            related = None
            wanted = _norm(str(classification.get("related_entity") or ""))
            for cls in version.classes:
                if _norm(cls.name) == wanted or _norm(cls.normalized_name) == wanted:
                    related = cls.id
                    break
            element_id = f"con_{uuid.uuid4().hex[:10]}"
            version.constraints.append(
                OntologyConstraint(
                    id=element_id,
                    constraint_type=OntologyConstraintType.BUSINESS_RULE,
                    expression=expression,
                    related_class_id=related,
                    evidence=evidence,
                    confidence_score=0.75,
                    status=OntologyElementStatus.DRAFT,
                    created_at=now,
                    updated_at=now,
                )
            )
    else:
        raise ValueError("This correction is not an ontology alias or rule.")
    version.updated_at = now
    ontology_db_repository.save_version(version)
    return {"ontology_version_id": version.id, "element_id": element_id, "is_draft": version.is_draft}


def approved_contract_lines(version) -> list:
    """Rules and aliases on an approved version, ready for the context envelope."""
    if version is None or version.is_draft:
        return []
    lines = []
    for constraint in version.constraints or []:
        if constraint.status == OntologyElementStatus.REJECTED:
            continue
        expression = (constraint.expression or "").strip()
        if expression:
            lines.append(f"Rule: {expression}")
    for attribute in version.attributes or []:
        if attribute.status == OntologyElementStatus.REJECTED:
            continue
        for alias in attribute.aliases or []:
            if str(alias).strip():
                lines.append(f"Alias: {alias} means {attribute.attribute_name}")
    return lines


def approved_rules_for_discovery(version) -> list:
    """Constraints the next schema discovery should carry forward."""
    if version is None:
        return []
    rules = []
    class_names = {c.id: c.name for c in (version.classes or [])}
    for constraint in version.constraints or []:
        if constraint.status == OntologyElementStatus.REJECTED:
            continue
        expression = (constraint.expression or "").strip()
        if not expression:
            continue
        rules.append({
            "expression": expression,
            "constraint_type": getattr(constraint.constraint_type, "value", constraint.constraint_type) or "business_rule",
            "related_entity": class_names.get(constraint.related_class_id),
            "confidence": constraint.confidence_score,
        })
    return rules
