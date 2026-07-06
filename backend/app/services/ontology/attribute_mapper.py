"""Map attribute candidates to class/entity IDs."""
import uuid
from typing import Any, Dict, List, Optional

from app.models.ontology import ExtractionSourceType


class AttributeMapper:
    """Assign attributes to classes based on evidence context (snippet / xml_path)."""

    def map_attributes_to_classes(
        self,
        attributes: List[Dict[str, Any]],
        entities: List[Dict[str, Any]],
        xml_hierarchy: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        For each attribute, set class_id to best-matching entity (by xml_path parent or snippet).
        Returns list of attribute dicts with class_id set.
        """
        entity_by_id = {e["id"]: e for e in entities}
        # Map XML path to entity id (entities from XML have xml_path)
        entity_ids_by_xml_path: Dict[str, str] = {}
        for e in entities:
            path = e.get("xml_path")
            if path:
                entity_ids_by_xml_path[path] = e["id"]
        if xml_hierarchy:
            for node in xml_hierarchy:
                if not node.get("is_leaf"):
                    path = node.get("path")
                    if path and path not in entity_ids_by_xml_path and entities:
                        entity_ids_by_xml_path[path] = entities[0]["id"]

        result: List[Dict[str, Any]] = []
        for attr in attributes:
            class_id = None
            if attr.get("xml_path"):
                parent = "/".join(attr["xml_path"].rsplit("/", 1)[:-1])
                class_id = entity_ids_by_xml_path.get(parent)
            if not class_id and entities:
                # Fallback: assign to first entity or one mentioned in snippet
                snippet = (attr.get("evidence_snippet") or "").lower()
                for e in entities:
                    name = (e.get("normalized_name") or e.get("name", "")).lower()
                    if name and name in snippet:
                        class_id = e["id"]
                        break
                if not class_id:
                    class_id = entities[0]["id"]
            result.append({
                "id": attr.get("id") or f"attr_map_{uuid.uuid4().hex[:8]}",
                "class_id": class_id or (entities[0]["id"] if entities else ""),
                "attribute_name": attr.get("name") or attr.get("normalized_name", ""),
                "normalized_name": attr.get("normalized_name") or attr.get("name", ""),
                "data_type_guess": attr.get("data_type_guess"),
                "required_flag_guess": attr.get("required_flag_guess", False),
                "description": attr.get("description"),
                "evidence_snippet": attr.get("evidence_snippet") or (attr.get("evidence_snippets") or [" "])[0][:200],
                "confidence": attr.get("confidence", 0.5),
                "extraction_source": getattr(
                    ExtractionSourceType, str(attr.get("extraction_source", "COMBINED")).upper(), ExtractionSourceType.COMBINED
                ),
            })
        return result
