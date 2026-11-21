"""Push domain-pack business rules onto an ontology version as constraints."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.ontology import (
    OntologyConstraint,
    OntologyConstraintType,
    OntologyElementStatus,
    OntologyEvidence,
    OntologyVersion,
)
from app.services.domain_packs import detect_primary_pack, get_pack
from app.services.ontology.ontology_db_repository import ontology_db_repository

logger = logging.getLogger(__name__)

_TYPE_MAP = {
    "business_rule": OntologyConstraintType.BUSINESS_RULE,
    "required": OntologyConstraintType.REQUIRED,
    "unique": OntologyConstraintType.UNIQUE,
    "range": OntologyConstraintType.RANGE,
    "pattern": OntologyConstraintType.PATTERN,
    "reference": OntologyConstraintType.REFERENCE,
    "cardinality": OntologyConstraintType.CARDINALITY,
}


def _norm(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def _resolve_class_id(version: OntologyVersion, related_entity: Optional[str]) -> Optional[str]:
    if not related_entity:
        return None
    target = _norm(related_entity)
    for c in version.classes:
        if _norm(c.normalized_name) == target or _norm(c.name) == target:
            return c.id
    return None


def rules_from_domain_pack(pack_id: str = "healthcare_cost_of_care") -> List[Dict[str, Any]]:
    pack = get_pack(pack_id)
    if not pack:
        return []
    return list(pack.business_rules() or [])


def inject_business_rules(
    version: OntologyVersion,
    *,
    rules: Optional[List[Dict[str, Any]]] = None,
    pack_id: str = "healthcare_cost_of_care",
    replace_existing: bool = False,
    persist: bool = True,
) -> OntologyVersion:
    """Merge domain business rules into ``version.constraints`` and optionally persist."""
    incoming = rules if rules is not None else rules_from_domain_pack(pack_id)
    if not incoming:
        pack = detect_primary_pack(
            [a.attribute_name for a in version.attributes]
            + [c.normalized_name for c in version.classes]
        )
        if pack:
            incoming = list(pack.business_rules() or [])
            pack_id = pack.id

    existing_exprs = {
        (c.expression or "").strip().lower()
        for c in (version.constraints or [])
        if (c.expression or "").strip()
    }

    if replace_existing:
        version.constraints = [
            c
            for c in (version.constraints or [])
            if c.constraint_type != OntologyConstraintType.BUSINESS_RULE
            and "domain_pack" not in ((c.evidence[0].extraction_stage if c.evidence else "") or "")
        ]
        existing_exprs = {
            (c.expression or "").strip().lower()
            for c in version.constraints
        }

    now = datetime.utcnow()
    added = 0
    for rule in incoming:
        expression = str(rule.get("expression") or "").strip()
        if not expression:
            continue
        if expression.lower() in existing_exprs:
            continue
        ctype = _TYPE_MAP.get(
            str(rule.get("constraint_type") or "business_rule").lower(),
            OntologyConstraintType.BUSINESS_RULE,
        )
        related = _resolve_class_id(version, rule.get("related_entity"))
        evidence = [
            OntologyEvidence(
                id=f"evt_rule_{uuid.uuid4().hex[:8]}",
                artifact_id=f"domain_pack:{pack_id}",
                artifact_type="domain_pack",
                text_snippet=expression[:500],
                extraction_stage="domain_pack_business_rules",
            )
        ]
        version.constraints.append(
            OntologyConstraint(
                id=f"con_{uuid.uuid4().hex[:10]}",
                constraint_type=ctype,
                expression=expression[:500],
                related_class_id=related,
                evidence=evidence,
                confidence_score=float(rule.get("confidence") or 0.85),
                status=OntologyElementStatus.DRAFT,
                created_at=now,
                updated_at=now,
            )
        )
        existing_exprs.add(expression.lower())
        added += 1

    version.updated_at = now
    if persist:
        ontology_db_repository.save_version(version)
    logger.info(
        "Injected %d domain business rules from %s into %s (total constraints=%d)",
        added,
        pack_id,
        version.id,
        len(version.constraints or []),
    )
    return version
