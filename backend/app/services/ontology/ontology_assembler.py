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
                    parent_class_id=e.get("parent_class_id"),
                    source_evidence=ev_list,
                    confidence_score=float(e.get("confidence", 0.5)),
                    status=OntologyElementStatus.DRAFT,
                    created_at=now,
                    updated_at=now,
                    extraction_source=e.get("extraction_source", ExtractionSourceType.COMBINED),
                )
            )

        # A relationship or attribute is kept only when it names classes that
        # exist. Nothing is attached to a default class: an unbound element is
        # left out and reported, so the draft never states something no source said.
        class_ids = {c.id for c in classes}
        dropped: List[Dict[str, Any]] = []

        rels: List[OntologyRelationship] = []
        for r in relationships:
            if not r.get("relationship_name"):
                continue
            src_id = r.get("source_class_id") or ""
            tgt_id = r.get("target_class_id") or ""
            if src_id not in class_ids or tgt_id not in class_ids:
                dropped.append({
                    "kind": "relationship",
                    "name": r.get("relationship_name"),
                    "reason": "no named source and target entity",
                })
                continue
            if src_id == tgt_id:
                continue
            ev_list = self._evidence_for(r, evidence_pool)
            card = r.get("cardinality_if_detected") or r.get("cardinality")
            binding = r.get("tabular_binding")
            if binding is True:
                binding = {
                    "source_columns": r.get("source_columns") or [],
                    "target_columns": r.get("target_columns") or [],
                }
            elif not isinstance(binding, dict):
                binding = None
            rels.append(
                OntologyRelationship(
                    id=r.get("id") or f"rel_{uuid.uuid4().hex[:8]}",
                    source_class_id=src_id,
                    relationship_name=r.get("relationship_name", ""),
                    target_class_id=tgt_id,
                    definition=r.get("definition"),
                    evidence=ev_list,
                    cardinality_if_detected=card,
                    confidence_score=float(r.get("confidence", 0.5)),
                    status=OntologyElementStatus.DRAFT,
                    extraction_source=r.get("extraction_source", ExtractionSourceType.COMBINED),
                    source_columns=[str(c) for c in (r.get("source_columns") or []) if c],
                    target_columns=[str(c) for c in (r.get("target_columns") or []) if c],
                    tabular_binding=binding,
                    created_at=now,
                    updated_at=now,
                )
            )

        attrs: List[OntologyAttribute] = []
        for a in attributes:
            if (a.get("class_id") or "") not in class_ids:
                dropped.append({
                    "kind": "attribute",
                    "name": a.get("attribute_name") or a.get("name"),
                    "reason": "no named entity",
                })
                continue
            ev_list = self._evidence_for(a, evidence_pool)
            attrs.append(
                OntologyAttribute(
                    id=a.get("id") or f"attr_{uuid.uuid4().hex[:8]}",
                    class_id=a["class_id"],
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
        type_map = {
            "business_rule": OntologyConstraintType.BUSINESS_RULE,
            "required": OntologyConstraintType.REQUIRED,
            "unique": OntologyConstraintType.UNIQUE,
            "range": OntologyConstraintType.RANGE,
            "pattern": OntologyConstraintType.PATTERN,
            "reference": OntologyConstraintType.REFERENCE,
            "cardinality": OntologyConstraintType.CARDINALITY,
        }
        class_by_norm = {
            "".join(ch for ch in (c.normalized_name or c.name or "").lower() if ch.isalnum()): c.id
            for c in classes
        }
        for br in business_rules:
            related_raw = str(br.get("related_entity") or br.get("related_class") or "").lower()
            related_key = "".join(ch for ch in related_raw if ch.isalnum())
            related_id = class_by_norm.get(related_key)
            ctype = type_map.get(
                str(br.get("constraint_type") or "business_rule").lower(),
                OntologyConstraintType.BUSINESS_RULE,
            )
            constraints.append(
                OntologyConstraint(
                    id=f"con_{uuid.uuid4().hex[:8]}",
                    constraint_type=ctype,
                    expression=br.get("expression", br.get("evidence_snippet", ""))[:500],
                    related_class_id=related_id,
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
            "dropped": dropped,
        }

    def _evidence_for(self, item: Dict[str, Any], pool: List[OntologyEvidence]) -> List[OntologyEvidence]:
        snippet = item.get("evidence_snippet") or (item.get("evidence_snippets") or [""])[0]
        evidence_meta = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        if not snippet and evidence_meta.get("detail"):
            snippet = evidence_meta["detail"]
        if not snippet and not item.get("xml_path"):
            return []
        for ev in pool:
            if ev.text_snippet and snippet and (
                ev.text_snippet[:100] in snippet or snippet[:100] in ev.text_snippet
            ):
                return [ev]
        if snippet:
            return [
                OntologyEvidence(
                    id=f"evt_asm_{uuid.uuid4().hex[:6]}",
                    artifact_id=str(item.get("artifact_id") or evidence_meta.get("basis") or ""),
                    artifact_type=str(item.get("artifact_type") or "profile"),
                    page_number=item.get("page_number"),
                    xml_path=item.get("xml_path"),
                    text_snippet=str(snippet)[:500],
                    extraction_stage="ontology_assembler",
                )
            ]
        return []
