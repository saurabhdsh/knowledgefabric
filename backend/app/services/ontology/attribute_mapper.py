"""Map attribute candidates to class/entity IDs."""
import uuid
from typing import Any, Dict, List, Optional

from app.models.ontology import ExtractionSourceType
from app.services.ontology.text_match import entity_names, find_mentions, resolve_name


class AttributeMapper:
    """Assign attributes to classes based on evidence context (snippet / xml_path)."""

    def __init__(self) -> None:
        self.last_unassigned: List[str] = []

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
        # Map XML path to entity id (entities from XML have xml_path)
        entity_ids_by_xml_path: Dict[str, str] = {}
        for e in entities:
            path = e.get("xml_path")
            if path:
                entity_ids_by_xml_path[path] = e["id"]
        names = entity_names(entities)
        # An XML element whose entity was merged with a same-named one keeps its fields.
        for node in xml_hierarchy or []:
            path = node.get("path")
            if node.get("is_leaf") or not path or path in entity_ids_by_xml_path:
                continue
            owner = resolve_name(str(node.get("tag") or path.rsplit("/", 1)[-1]), names)
            if owner:
                entity_ids_by_xml_path[path] = owner

        result: List[Dict[str, Any]] = []
        self.last_unassigned = []
        for attr in attributes:
            class_id = None
            # 1. The XML element that contains the field.
            if attr.get("xml_path"):
                parent = "/".join(attr["xml_path"].rsplit("/", 1)[:-1])
                class_id = entity_ids_by_xml_path.get(parent)
            # 2. The entity the extractor named for this field.
            if not class_id and attr.get("entity"):
                class_id = resolve_name(str(attr["entity"]), names)
            # 3. The first entity named, as a whole word, in the text the field came from.
            if not class_id:
                found = find_mentions(str(attr.get("evidence_snippet") or ""), names)
                if found:
                    class_id = found[0][2]
            if not class_id:
                # No source ties this field to an entity, so it is left out
                # instead of being attached to whichever entity came first.
                self.last_unassigned.append(attr.get("name") or attr.get("normalized_name") or "")
                continue
            result.append({
                "id": attr.get("id") or f"attr_map_{uuid.uuid4().hex[:8]}",
                "class_id": class_id,
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
