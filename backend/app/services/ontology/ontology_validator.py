"""Validate assembled ontology for consistency and completeness."""
from typing import Any, Dict, List, Tuple


class OntologyValidator:
    """Check referential integrity and basic consistency."""

    def validate(
        self,
        classes: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        attributes: List[Dict[str, Any]],
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Returns (is_valid, list of error/warning messages, stats).
        """
        errors: List[str] = []
        warnings: List[str] = []
        class_ids = {c["id"] for c in classes}

        for rel in relationships:
            if rel.get("source_class_id") and rel["source_class_id"] not in class_ids:
                errors.append(f"Relationship {rel.get('id')} source_class_id not in classes")
            if rel.get("target_class_id") and rel["target_class_id"] not in class_ids:
                errors.append(f"Relationship {rel.get('id')} target_class_id not in classes")

        for attr in attributes:
            if attr.get("class_id") and attr["class_id"] not in class_ids:
                errors.append(f"Attribute {attr.get('id')} class_id not in classes")

        if not classes:
            warnings.append("No entities/classes discovered")

        stats = {
            "classes_count": len(classes),
            "relationships_count": len(relationships),
            "attributes_count": len(attributes),
            "errors_count": len(errors),
            "warnings_count": len(warnings),
        }
        return (len(errors) == 0, errors + warnings, stats)
