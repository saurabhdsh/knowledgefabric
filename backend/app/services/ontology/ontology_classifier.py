"""Classify raw candidates into entity / relationship / attribute / rule / enumeration."""
from typing import Any, Dict, List, Optional

from app.models.ontology import ExtractionSourceType


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

    def _merge_by_normalized(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_norm: Dict[str, Dict[str, Any]] = {}
        for it in items:
            norm = (it.get("normalized_name") or it.get("name") or "").strip()
            if not norm:
                continue
            if norm not in by_norm:
                it["evidence_snippets"] = [it.get("evidence_snippet", "")[:200]]
                it["source_count"] = 1
                by_norm[norm] = it
            else:
                existing = by_norm[norm]
                existing["confidence"] = max(
                    existing.get("confidence", 0), it.get("confidence", 0)
                )
                existing.setdefault("evidence_snippets", []).append(
                    (it.get("evidence_snippet") or "")[:200]
                )
                existing["source_count"] = existing.get("source_count", 1) + 1
        return list(by_norm.values())

    def _score_repetition(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for it in items:
            count = it.get("source_count", 1)
            base = it.get("confidence", 0.5)
            # Slight boost for repetition
            it["confidence"] = min(1.0, base + 0.05 * (count - 1))
        return items
