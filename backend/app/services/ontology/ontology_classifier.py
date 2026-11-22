"""Classify raw candidates into entity / relationship / attribute / rule / enumeration."""
from typing import Any, Dict, List, Optional

from app.models.ontology import ExtractionSourceType
from app.services.ontology.text_match import canonical_key

REPEAT_BOOST = 0.05
REPEAT_BOOST_CAP = 0.15


class OntologyClassifier:
    """Assigns candidate type and refines confidence using repetition and structure."""

    def classify_candidates(
        self,
        rule_based: Dict[str, List[Dict[str, Any]]],
        llm_candidates: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Merge rule-based and LLM candidates, dedupe by normalized name, assign final type.
        Returns classified dict: entities, relationships, attributes, business_rules, enumerations.
        """
        llm = llm_candidates or {}
        # Merge and group by normalized name
        entities = self._merge_by_normalized(
            rule_based.get("entities", []) + llm.get("entities", [])
        )
        relationships = self._merge_by_normalized(
            rule_based.get("relationships", []) + llm.get("relationships", [])
        )
        attributes = self._merge_by_normalized(
            rule_based.get("attributes", []) + llm.get("attributes", [])
        )
        business_rules = rule_based.get("business_rules", []) + llm.get("business_rules", [])
        enumerations = rule_based.get("enumerations", []) + llm.get("enumerations", [])

        # Boost confidence for repeated entities
        entities = self._score_repetition(entities)
        attributes = self._score_repetition(attributes)
        relationships = self._score_repetition(relationships)

        return {
            "entities": entities,
            "relationships": relationships,
            "attributes": attributes,
            "business_rules": business_rules[:50],
            "enumerations": enumerations[:30],
        }

    @staticmethod
    def _merge_key(it: Dict[str, Any]) -> str:
        """Names that differ only by case or plural are one candidate.

        A relationship with named ends is a different fact for each pair of
        ends, so "Provider submits Claim" and "Member submits Appeal" stay apart.
        """
        norm = canonical_key(it.get("normalized_name") or it.get("name") or "")
        if it.get("subject") and it.get("object"):
            return f"{canonical_key(it['subject'])}|{norm}|{canonical_key(it['object'])}"
        return norm

    def _merge_by_normalized(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_norm: Dict[str, Dict[str, Any]] = {}
        for it in items:
            norm = self._merge_key(it)
            if not norm:
                continue
            if norm not in by_norm:
                it["evidence_snippets"] = [(it.get("evidence_snippet") or "")[:300]]
                it["source_count"] = 1
                by_norm[norm] = it
            else:
                existing = by_norm[norm]
                existing["confidence"] = max(
                    existing.get("confidence", 0), it.get("confidence", 0)
                )
                snippet = (it.get("evidence_snippet") or "")[:300]
                if snippet and snippet not in existing.setdefault("evidence_snippets", []):
                    existing["evidence_snippets"].append(snippet)
                    existing["source_count"] = existing.get("source_count", 1) + 1
                if not existing.get("evidence_snippet") and snippet:
                    existing["evidence_snippet"] = snippet
                for field in ("definition", "entity", "xml_path"):
                    if not existing.get(field) and it.get(field):
                        existing[field] = it[field]
        return list(by_norm.values())

    def _score_repetition(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Each further distinct passage that states the same thing adds a little, up to +0.15."""
        for it in items:
            count = it.get("source_count", 1)
            base = it.get("confidence", 0.5)
            it["confidence"] = min(1.0, base + min(REPEAT_BOOST_CAP, REPEAT_BOOST * (count - 1)))
        return items
