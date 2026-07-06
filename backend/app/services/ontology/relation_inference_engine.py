"""Infer relationships between entities from text and structure."""
import re
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.models.ontology import OntologyEvidence, ExtractionSourceType


class RelationInferenceEngine:
    """Infer source_class_id -> relationship_name -> target_class_id from co-occurrence and verbs."""

    def infer_relationships(
        self,
        entities: List[Dict[str, Any]],
        relationship_candidates: List[Dict[str, Any]],
        text_chunks: List[Dict[str, Any]],
        evidence_factory: Optional[Callable[..., OntologyEvidence]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Produce list of {source_class_id, relationship_name, target_class_id, confidence, evidence}.
        evidence_factory(artifact_id, snippet) -> OntologyEvidence.
        """
        result: List[Dict[str, Any]] = []
        entity_by_name: Dict[str, str] = {}
        for e in entities:
            name = (e.get("normalized_name") or e.get("name", "")).strip()
            if name and "id" in e:
                entity_by_name[name.lower()] = e["id"]

        # Use relationship name candidates and try to bind source/target from context
        for rel_cand in relationship_candidates[:40]:
            name = rel_cand.get("normalized_name") or rel_cand.get("name", "")
            snippet = rel_cand.get("evidence_snippet", "") or rel_cand.get("evidence_snippets", [" "])[0]
            # Try to find two entity names in snippet
            found = self._find_entity_pair_in_text(snippet, entity_by_name)
            if found:
                source_id, target_id = found
                result.append({
                    "id": f"rel_inf_{uuid.uuid4().hex[:8]}",
                    "source_class_id": source_id,
                    "relationship_name": name,
                    "target_class_id": target_id,
                    "definition": None,
                    "evidence_snippet": snippet[:300],
                    "confidence": rel_cand.get("confidence", 0.5) * 0.9,
                    "extraction_source": ExtractionSourceType.COMBINED,
                })
            else:
                # Add unbound relationship for later manual mapping
                result.append({
                    "id": f"rel_inf_{uuid.uuid4().hex[:8]}",
                    "source_class_id": None,
                    "relationship_name": name,
                    "target_class_id": None,
                    "definition": None,
                    "evidence_snippet": snippet[:300],
                    "confidence": rel_cand.get("confidence", 0.4),
                    "extraction_source": ExtractionSourceType.COMBINED,
                })

        return result

    def bind_tabular_relationship_candidates(
        self,
        entities: List[Dict[str, Any]],
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Resolve FK-style tabular relationships using inferred entity display names."""
        by_display: Dict[str, str] = {}
        for e in entities:
            for key in (
                (e.get("normalized_name") or "").strip(),
                (e.get("name") or "").strip(),
            ):
                if key:
                    by_display[key.lower()] = e.get("id")

        result: List[Dict[str, Any]] = []
        for r in candidates:
            if not r.get("tabular_binding"):
                continue
            sn = (r.get("source_entity_normalized") or "").strip()
            tn = (r.get("target_entity_normalized") or "").strip()
            sid = by_display.get(sn.lower())
            tid = by_display.get(tn.lower())
            if not sid or not tid:
                continue
            nm = r.get("relationship_name") or r.get("name") or "references"
            result.append({
                "id": r.get("id") or f"rel_tab_{uuid.uuid4().hex[:8]}",
                "source_class_id": sid,
                "relationship_name": nm,
                "target_class_id": tid,
                "definition": None,
                "evidence_snippet": (r.get("evidence_snippet") or "")[:300],
                "confidence": float(r.get("confidence", 0.8)),
                "extraction_source": ExtractionSourceType.COMBINED,
            })
        return result

    def _find_entity_pair_in_text(
        self, text: str, entity_by_name: Dict[str, str]
    ) -> Optional[Tuple[str, str]]:
        """Find first two entities mentioned in text (order preserved)."""
        found_ids: List[str] = []
        lower = text.lower()
        for name, eid in entity_by_name.items():
            if name in lower:
                found_ids.append(eid)
                if len(found_ids) >= 2:
                    return (found_ids[0], found_ids[1])
        return None
