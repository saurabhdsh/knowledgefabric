"""Export ontology to JSON, CSV, and graph-ready formats; canonical model generation."""
import csv
import io
import json
from typing import Any, Dict, List, Optional

from app.models.ontology import (
    OntologyVersion,
    OntologyClass,
    OntologyRelationship,
    OntologyAttribute,
    OntologyConstraint,
)


class OntologyExportService:
    """Export and canonical model generation."""

    def export_json(self, version: OntologyVersion) -> Dict[str, Any]:
        """Full ontology as JSON (exportable ontology JSON)."""
        return {
            "version_id": version.id,
            "project_id": version.project_id,
            "version_label": version.version_label,
            "is_draft": version.is_draft,
            "entities": [self._class_to_dict(c) for c in version.classes],
            "relationships": [self._rel_to_dict(r) for r in version.relationships],
            "attributes": [self._attr_to_dict(a) for a in version.attributes],
            "constraints": [self._constraint_to_dict(c) for c in version.constraints],
            "created_at": version.created_at.isoformat() if version.created_at else None,
            "updated_at": version.updated_at.isoformat() if version.updated_at else None,
        }

    def export_csv(self, version: OntologyVersion) -> str:
        """Multi-sheet-like CSV: entities, relationships, attributes as separate sections."""
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Section", "Entity Catalog"])
        w.writerow(["id", "name", "normalized_name", "definition", "confidence_score", "status"])
        for c in version.classes:
            w.writerow([
                c.id, c.name, c.normalized_name, (c.definition or "")[:200],
                c.confidence_score, c.status.value,
            ])
        w.writerow([])
        w.writerow(["Section", "Relationship Matrix"])
        w.writerow(["id", "source_class_id", "relationship_name", "target_class_id", "confidence_score", "status"])
        for r in version.relationships:
            w.writerow([
                r.id, r.source_class_id, r.relationship_name, r.target_class_id,
                r.confidence_score, r.status.value,
            ])
        w.writerow([])
        w.writerow(["Section", "Attribute Catalog"])
        w.writerow(["id", "class_id", "attribute_name", "normalized_name", "data_type_guess", "required_flag_guess", "confidence_score", "status"])
        for a in version.attributes:
            w.writerow([
                a.id, a.class_id, a.attribute_name, a.normalized_name,
                a.data_type_guess or "", a.required_flag_guess, a.confidence_score, a.status.value,
            ])
        return buf.getvalue()

    def export_graph(self, version: OntologyVersion) -> Dict[str, Any]:
        """Graph-ready payload: node types, edge types, properties, validation rules, Neo4j-style snippet."""
        node_types = []
        for c in version.classes:
            props = []
            for a in version.attributes:
                if a.class_id == c.id:
                    props.append({
                        "name": a.attribute_name,
                        "data_type": a.data_type_guess or "string",
                        "required": a.required_flag_guess,
                    })
            node_types.append({
                "type": c.normalized_name,
                "label": c.name,
                "definition": c.definition,
                "properties": props,
            })
        edge_types = []
        for r in version.relationships:
            src = self._class_id_to_name(r.source_class_id, version.classes)
            tgt = self._class_id_to_name(r.target_class_id, version.classes)
            edge_types.append({
                "source_type": src,
                "edge_label": r.relationship_name,
                "target_type": tgt,
                "cardinality": r.cardinality_if_detected,
            })
        validation_rules = [
            {"constraint_type": c.constraint_type.value, "expression": c.expression}
            for c in version.constraints
        ]
        graph_cypher_snippet = self._build_graph_cypher_snippet(version)
        graph_json_schema = {
            "nodes": [{"id": c.normalized_name, "label": c.name} for c in version.classes],
            "edges": [
                {"from": self._class_id_to_name(r.source_class_id, version.classes), "to": self._class_id_to_name(r.target_class_id, version.classes), "label": r.relationship_name}
                for r in version.relationships
            ],
        }
        return {
            "node_types": node_types,
            "edge_types": edge_types,
            "validation_rules": validation_rules,
            "version_id": version.id,
            "graph_cypher_snippet": graph_cypher_snippet,
            "graph_json_schema": graph_json_schema,
        }

    def _build_graph_cypher_snippet(self, version: OntologyVersion) -> str:
        """Neo4j-style Cypher snippet for node and relationship types (schema hint)."""
        lines = ["// Graph-ready ontology (Neo4j / Cypher-style)", "// Node labels: " + ", ".join(c.normalized_name for c in version.classes)]
        for r in version.relationships:
            src = self._class_id_to_name(r.source_class_id, version.classes)
            tgt = self._class_id_to_name(r.target_class_id, version.classes)
            rel = (r.relationship_name or "RELATES_TO").upper().replace(" ", "_")
            lines.append(f"// ({src})-[{rel}]->({tgt})")
        return "\n".join(lines)

    def canonical_model(self, version: OntologyVersion) -> Dict[str, Any]:
        """Canonical data model: entity catalog, relationship matrix, attribute catalog, suggested schemas."""
        entity_catalog = [
            {"id": c.id, "name": c.name, "normalized_name": c.normalized_name, "definition": c.definition}
            for c in version.classes
        ]
        relationship_matrix = [
            {
                "source": self._class_id_to_name(r.source_class_id, version.classes),
                "relationship": r.relationship_name,
                "target": self._class_id_to_name(r.target_class_id, version.classes),
                "cardinality": r.cardinality_if_detected,
            }
            for r in version.relationships
        ]
        attribute_catalog = []
        for a in version.attributes:
            class_name = self._class_id_to_name(a.class_id, version.classes)
            attribute_catalog.append({
                "class": class_name,
                "attribute_name": a.attribute_name,
                "data_type": a.data_type_guess or "string",
                "required": a.required_flag_guess,
            })
        suggested_tables = [
            {"table_name": c.normalized_name.lower().replace(" ", "_"), "entity_id": c.id}
            for c in version.classes
        ]
        suggested_doc_schema = {
            "type": "object",
            "properties": {
                c.normalized_name: {"type": "object", "description": c.definition or c.name}
                for c in version.classes
            },
        }
        suggested_sql_ddl = self._build_suggested_sql_ddl(version)
        return {
            "entity_catalog": entity_catalog,
            "relationship_matrix": relationship_matrix,
            "attribute_catalog": attribute_catalog,
            "suggested_relational_tables": suggested_tables,
            "suggested_document_schema": suggested_doc_schema,
            "suggested_sql_ddl": suggested_sql_ddl,
            "graph_schema": self.export_graph(version),
        }

    def _build_suggested_sql_ddl(self, version: OntologyVersion) -> str:
        """Suggested SQL DDL statements for relational implementation."""
        lines = ["-- Canonical data model: suggested relational schema", ""]
        for c in version.classes:
            table = c.normalized_name.lower().replace(" ", "_")
            lines.append(f"CREATE TABLE {table} (")
            pk = None
            attrs = [a for a in version.attributes if a.class_id == c.id]
            for i, a in enumerate(attrs):
                col = (a.attribute_name or a.normalized_name).lower().replace(" ", "_")
                if col in ("id", "id_") or a.attribute_name and "id" in a.attribute_name.lower():
                    pk = col
                dtype = (a.data_type_guess or "VARCHAR(255)").upper()
                if dtype not in ("INTEGER", "BIGINT", "VARCHAR(255)", "TEXT", "DATE", "TIMESTAMP", "BOOLEAN", "DECIMAL"):
                    dtype = "VARCHAR(255)"
                req = " NOT NULL" if a.required_flag_guess else ""
                lines.append(f"  {col} {dtype}{req},")
            if attrs:
                lines[-1] = lines[-1].rstrip(",")
            if pk:
                lines.append(f"  PRIMARY KEY ({pk})")
            lines.append(");")
            lines.append("")
        return "\n".join(lines)

    def _class_to_dict(self, c: OntologyClass) -> Dict[str, Any]:
        return {
            "id": c.id, "name": c.name, "normalized_name": c.normalized_name,
            "definition": c.definition, "aliases": c.aliases,
            "confidence_score": c.confidence_score, "status": c.status.value,
            "source_evidence": [{"text_snippet": e.text_snippet[:200], "page_number": e.page_number, "xml_path": e.xml_path} for e in c.source_evidence],
        }

    def _rel_to_dict(self, r: OntologyRelationship) -> Dict[str, Any]:
        return {
            "id": r.id, "source_class_id": r.source_class_id, "relationship_name": r.relationship_name,
            "target_class_id": r.target_class_id, "cardinality_if_detected": r.cardinality_if_detected,
            "confidence_score": r.confidence_score, "status": r.status.value,
        }

    def _attr_to_dict(self, a: OntologyAttribute) -> Dict[str, Any]:
        return {
            "id": a.id, "class_id": a.class_id, "attribute_name": a.attribute_name,
            "normalized_name": a.normalized_name, "data_type_guess": a.data_type_guess,
            "required_flag_guess": a.required_flag_guess, "confidence_score": a.confidence_score,
            "status": a.status.value,
        }

    def _constraint_to_dict(self, c: OntologyConstraint) -> Dict[str, Any]:
        return {"id": c.id, "constraint_type": c.constraint_type.value, "expression": c.expression}

    def _class_id_to_name(self, class_id: str, classes: List[OntologyClass]) -> str:
        for c in classes:
            if c.id == class_id:
                return c.normalized_name
        return class_id
