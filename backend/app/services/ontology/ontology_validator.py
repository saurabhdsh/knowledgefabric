"""Validate an assembled ontology against itself and, when given, against the data.

Referential checks always run. When a measured table profile is supplied, the
validator also checks cardinality, required fields, and duplicate class names
against the rows — so a draft that disagrees with the data is marked, not
silently accepted.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.services.ontology.text_match import canonical_key


class OntologyValidator:
    """Check referential integrity and, optionally, agreement with the table profile."""

    def validate(
        self,
        classes: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        attributes: List[Dict[str, Any]],
        *,
        profile: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Returns ``(is_valid, messages, stats)``.

        Errors make ``is_valid`` false. Warnings are listed but do not fail the
        draft — they are things a reviewer should look at.
        """
        errors: List[str] = []
        warnings: List[str] = []
        class_ids = {c["id"] for c in classes if c.get("id")}
        class_by_id = {c["id"]: c for c in classes if c.get("id")}

        for rel in relationships:
            if rel.get("source_class_id") and rel["source_class_id"] not in class_ids:
                errors.append(f"Relationship {rel.get('id')} source_class_id not in classes")
            if rel.get("target_class_id") and rel["target_class_id"] not in class_ids:
                errors.append(f"Relationship {rel.get('id')} target_class_id not in classes")
            if not rel.get("source_class_id") or not rel.get("target_class_id"):
                errors.append(f"Relationship {rel.get('id') or rel.get('relationship_name')} has no named ends")

        for attr in attributes:
            if attr.get("class_id") and attr["class_id"] not in class_ids:
                errors.append(f"Attribute {attr.get('id')} class_id not in classes")
            if not attr.get("class_id"):
                errors.append(f"Attribute {attr.get('id') or attr.get('attribute_name')} has no named entity")

        for cls in classes:
            parent = cls.get("parent_class_id")
            if parent and parent not in class_ids:
                errors.append(f"Class {cls.get('id')} parent_class_id not in classes")
            if parent and parent == cls.get("id"):
                errors.append(f"Class {cls.get('id')} cannot be its own parent")

        if not classes:
            warnings.append("No entities/classes discovered")

        # Duplicate class names (same concept listed twice).
        by_name: Dict[str, List[str]] = {}
        for cls in classes:
            key = canonical_key(cls.get("normalized_name") or cls.get("name") or "")
            if key:
                by_name.setdefault(key, []).append(cls.get("id") or "")
        for name, ids in by_name.items():
            if len(ids) > 1:
                warnings.append(f"Duplicate class name '{name}' on {', '.join(ids)}")

        if profile:
            self._check_against_profile(
                classes, relationships, attributes, profile, class_by_id, errors, warnings
            )

        stats = {
            "classes_count": len(classes),
            "relationships_count": len(relationships),
            "attributes_count": len(attributes),
            "errors_count": len(errors),
            "warnings_count": len(warnings),
            "checked_against_data": bool(profile),
        }
        return (len(errors) == 0, errors + warnings, stats)

    def _check_against_profile(
        self,
        classes: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        attributes: List[Dict[str, Any]],
        profile: Dict[str, Any],
        class_by_id: Dict[str, Dict[str, Any]],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        tables = {t["name"]: t for t in profile.get("tables") or []}
        # Map class → table by normalized name.
        class_table: Dict[str, Dict[str, Any]] = {}
        for cls in classes:
            name = str(cls.get("normalized_name") or cls.get("name") or "")
            for table_name, table in tables.items():
                if canonical_key(table_name) == canonical_key(name):
                    class_table[cls["id"]] = table
                    break

        # Required attributes must be non-null in the data.
        for attr in attributes:
            if not attr.get("required_flag_guess"):
                continue
            table = class_table.get(attr.get("class_id") or "")
            if not table:
                continue
            col = next(
                (c for c in table["columns"] if canonical_key(c["name"]) == canonical_key(attr.get("attribute_name") or attr.get("name") or "")),
                None,
            )
            if col is None:
                warnings.append(
                    f"Required attribute {attr.get('attribute_name')} on {table['name']} "
                    "is not a column in the measured profile"
                )
                continue
            if col.get("null_count", 0) > 0:
                warnings.append(
                    f"Attribute {table['name']}.{col['name']} is marked required but "
                    f"{col['null_count']} of {table['row_count']} rows are empty"
                )

        # Cardinality on tabular relationships must match uniqueness of the child column.
        fk_by_cols = {
            (fk["from_table"], fk["from_column"], fk["to_table"], fk["to_column"]): fk
            for fk in profile.get("foreign_keys") or []
        }
        for rel in relationships:
            src = class_by_id.get(rel.get("source_class_id") or "")
            tgt = class_by_id.get(rel.get("target_class_id") or "")
            if not src or not tgt:
                continue
            src_table = class_table.get(src["id"])
            tgt_table = class_table.get(tgt["id"])
            if not src_table or not tgt_table:
                continue
            src_cols = [str(c) for c in (rel.get("source_columns") or []) if c]
            tgt_cols = [str(c) for c in (rel.get("target_columns") or []) if c]
            if len(src_cols) != 1 or len(tgt_cols) != 1:
                continue
            fk = fk_by_cols.get((src_table["name"], src_cols[0], tgt_table["name"], tgt_cols[0]))
            if not fk:
                continue
            card = str(rel.get("cardinality_if_detected") or rel.get("cardinality") or "").lower()
            measured = str(fk.get("cardinality") or "").lower()
            if card in ("1:1", "1-1", "one-to-one") and measured not in ("one-to-one", "1:1"):
                warnings.append(
                    f"Relationship {rel.get('relationship_name')} is marked 1:1 but the data "
                    f"shows {fk['from_table']}.{fk['from_column']} is not unique"
                )
            if fk.get("orphan_values"):
                warnings.append(
                    f"Relationship {rel.get('relationship_name')}: "
                    f"{fk['orphan_values']} value(s) of {fk['from_table']}.{fk['from_column']} "
                    "have no matching parent row"
                )
            if fk.get("support") == "low":
                warnings.append(
                    f"Relationship {rel.get('relationship_name')} rests on only "
                    f"{fk.get('distinct_values')} distinct value(s)"
                )
