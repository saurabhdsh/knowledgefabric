"""Assemble classified candidates and inferred relations into OntologyVersion model."""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.ontology import (
    OntologyClass,
    OntologyRelationship,
    OntologyAttribute,
    OntologyConstraint,
    OntologyEvidence,
    OntologyElementStatus,
    OntologyConstraintType,
    ExtractionSourceType,
)


class OntologyAssembler:
    """Build OntologyClass, OntologyRelationship, OntologyAttribute, OntologyConstraint from pipeline output."""

    def assemble(
        self,
        project_id: str,
        version_label: str,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        attributes: List[Dict[str, Any]],
        business_rules: List[Dict[str, Any]],
        evidence_pool: Optional[List[OntologyEvidence]] = None,
    ) -> Dict[str, Any]:
        """
        Returns dict with classes, relationships, attributes, constraints
        (Pydantic model-compatible dicts).
        """
        evidence_pool = evidence_pool or []
        now = datetime.utcnow()

        classes: List[OntologyClass] = []
        for e in entities:
            ev_list = self._evidence_for(e, evidence_pool)
            classes.append(
                OntologyClass(
                    id=e.get("id") or f"cls_{uuid.uuid4().hex[:8]}",
                    name=e.get("name") or e.get("normalized_name", ""),
                    normalized_name=e.get("normalized_name") or e.get("name", ""),
                    definition=e.get("definition"),
                    aliases=e.get("aliases", []),
                    source_evidence=ev_list,
                    confidence_score=float(e.get("confidence", 0.5)),
                    status=OntologyElementStatus.DRAFT,
                    created_at=now,
                    updated_at=now,
                    extraction_source=e.get("extraction_source", ExtractionSourceType.COMBINED),
                )
            )

        rels: List[OntologyRelationship] = []
        for r in relationships:
            if not r.get("relationship_name"):
                continue
            ev_list = self._evidence_for(r, evidence_pool)
            rels.append(
                OntologyRelationship(
                    id=r.get("id") or f"rel_{uuid.uuid4().hex[:8]}",
                    source_class_id=r.get("source_class_id") or (classes[0].id if classes else ""),
                    relationship_name=r.get("relationship_name", ""),
                    target_class_id=r.get("target_class_id") or (classes[1].id if len(classes) > 1 else (classes[0].id if classes else "")),
                    definition=r.get("definition"),
                    evidence=ev_list,
                    cardinality_if_detected=r.get("cardinality_if_detected"),
                    confidence_score=float(r.get("confidence", 0.5)),
                    status=OntologyElementStatus.DRAFT,
                    extraction_source=r.get("extraction_source", ExtractionSourceType.COMBINED),
                    created_at=now,
                    updated_at=now,
                )
            )

        attrs: List[OntologyAttribute] = []
        for a in attributes:
            ev_list = self._evidence_for(a, evidence_pool)
            attrs.append(
                OntologyAttribute(
                    id=a.get("id") or f"attr_{uuid.uuid4().hex[:8]}",
                    class_id=a.get("class_id") or (classes[0].id if classes else ""),
                    attribute_name=a.get("attribute_name") or a.get("name", ""),
                    normalized_name=a.get("normalized_name") or a.get("attribute_name", ""),
                    data_type_guess=a.get("data_type_guess"),
                    required_flag_guess=a.get("required_flag_guess", False),
                    description=a.get("description"),
                    evidence=ev_list,
                    confidence_score=float(a.get("confidence", 0.5)),
                    status=OntologyElementStatus.DRAFT,
                    extraction_source=a.get("extraction_source", ExtractionSourceType.COMBINED),
                    created_at=now,
                    updated_at=now,
                )
            )

        constraints: List[OntologyConstraint] = []
        for br in business_rules:
            constraints.append(
                OntologyConstraint(
                    id=f"con_{uuid.uuid4().hex[:8]}",
                    constraint_type=OntologyConstraintType.BUSINESS_RULE,
                    expression=br.get("expression", br.get("evidence_snippet", "")[:500]),
                    evidence=self._evidence_for(br, evidence_pool),
                    confidence_score=float(br.get("confidence", 0.5)),
                    status=OntologyElementStatus.DRAFT,
                    created_at=now,
                    updated_at=now,
                )
            )

        return {
            "classes": [c.model_dump() for c in classes],
            "relationships": [r.model_dump() for r in rels],
            "attributes": [a.model_dump() for a in attrs],
            "constraints": [c.model_dump() for c in constraints],
        }

    def _evidence_for(self, item: Dict[str, Any], pool: List[OntologyEvidence]) -> List[OntologyEvidence]:
        snippet = item.get("evidence_snippet") or (item.get("evidence_snippets") or [""])[0]
        if not snippet and not item.get("xml_path"):
            return []
        # Create a minimal evidence if we have snippet and no pool match
        for ev in pool:
            if ev.text_snippet and snippet and ev.text_snippet[:100] in snippet or (snippet and snippet[:100] in ev.text_snippet):
                return [ev]
        if snippet:
            return [
                OntologyEvidence(
                    id=f"evt_asm_{uuid.uuid4().hex[:6]}",
                    artifact_id=item.get("artifact_id", ""),
                    artifact_type=item.get("artifact_type", "unknown"),
                    page_number=item.get("page_number"),
                    xml_path=item.get("xml_path"),
                    text_snippet=str(snippet)[:500],
                    extraction_stage="ontology_assembler",
                )
            ]
        return []
