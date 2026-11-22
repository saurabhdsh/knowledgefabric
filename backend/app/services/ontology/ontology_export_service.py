"""Export ontology to JSON, CSV, RDF/Turtle, OWL, and graph-ready formats."""
import csv
import io
import re
from typing import Any, Dict, List, Optional

from app.models.ontology import (
    OntologyVersion,
    OntologyClass,
    OntologyRelationship,
    OntologyAttribute,
    OntologyConstraint,
)

WEAVE_ONT_NS = "http://weave.ai/ontology/"


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

    def export_rdf_turtle(self, version: OntologyVersion) -> str:
        """Export ontology as RDF Schema Turtle (.ttl)."""
        base = f"{WEAVE_ONT_NS}{version.project_id}/"
        lines = [
            f"@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
            f"@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            f"@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            f"@prefix weave: <{base}> .",
            "",
            f"<{base}> a rdfs:Class ;",
            f'  rdfs:label "{self._ttl_esc(version.version_label or "ontology")}" ;',
            f'  rdfs:comment "Knowledge Fabric ontology export ({version.id})" .',
            "",
        ]
        class_local: Dict[str, str] = {
            c.id: self._safe_local(c.normalized_name or c.name or c.id) for c in version.classes
        }
        for c in version.classes:
            local = class_local[c.id]
            lines.append(f"weave:{local} a rdfs:Class ;")
            lines.append(f'  rdfs:label "{self._ttl_esc(c.name or c.normalized_name)}" ;')
            if c.definition:
                lines.append(f'  rdfs:comment "{self._ttl_esc(c.definition)}" ;')
            parent = class_local.get(getattr(c, "parent_class_id", None) or "")
            if parent:
                lines.append(f"  rdfs:subClassOf weave:{parent} ;")
            lines.append(f'  weave:confidence "{c.confidence_score:.4f}"^^xsd:decimal ;')
            lines.append(f'  weave:status "{self._ttl_esc(getattr(c.status, "value", str(c.status)))}" .')
            lines.append("")

        used_preds: Dict[str, int] = {}
        for r in version.relationships:
            base_pred = self._safe_local(r.relationship_name or r.id)
            n = used_preds.get(base_pred, 0)
            used_preds[base_pred] = n + 1
            # Two links that share a name (claims→members via member_id and
            # via subscriber_id) must not overwrite each other's domain.
            pred = base_pred if n == 0 else f"{base_pred}_{n + 1}"
            src = class_local.get(r.source_class_id) or self._safe_local(r.source_class_id)
            tgt = class_local.get(r.target_class_id) or self._safe_local(r.target_class_id)
            lines.append(f"weave:{pred} a rdf:Property ;")
            lines.append(f'  rdfs:label "{self._ttl_esc(r.relationship_name)}" ;')
            lines.append(f"  rdfs:domain weave:{src} ;")
            lines.append(f"  rdfs:range weave:{tgt} ;")
            if r.cardinality_if_detected:
                lines.append(f'  weave:cardinality "{self._ttl_esc(r.cardinality_if_detected)}" ;')
            lines.append(f'  weave:confidence "{r.confidence_score:.4f}"^^xsd:decimal .')
            lines.append("")

        for a in version.attributes:
            local = self._safe_local(f"{a.class_id}_{a.attribute_name or a.normalized_name or a.id}")
            domain = class_local.get(a.class_id) or self._safe_local(a.class_id)
            xsd_t = self._xsd_type(a.data_type_guess)
            lines.append(f"weave:{local} a rdf:Property ;")
            lines.append(f'  rdfs:label "{self._ttl_esc(a.attribute_name or a.normalized_name)}" ;')
            lines.append(f"  rdfs:domain weave:{domain} ;")
            lines.append(f"  rdfs:range {xsd_t} ;")
            if a.required_flag_guess:
                lines.append('  weave:required "true"^^xsd:boolean ;')
            lines.append(f'  weave:confidence "{a.confidence_score:.4f}"^^xsd:decimal .')
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def export_owl(self, version: OntologyVersion) -> str:
        """Export ontology as OWL 2 Turtle (.owl.ttl / .owl)."""
        base = f"{WEAVE_ONT_NS}{version.project_id}/"
        ont_iri = f"{base}ontology"
        lines = [
            f"@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
            f"@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            f"@prefix owl: <http://www.w3.org/2002/07/owl#> .",
            f"@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            f"@prefix weave: <{base}> .",
            "",
            f"<{ont_iri}> a owl:Ontology ;",
            f'  rdfs:label "{self._ttl_esc(version.version_label or "Ontology")}" ;',
            f'  owl:versionInfo "{self._ttl_esc(version.id)}" ;',
            f'  rdfs:comment "OWL export of Knowledge Fabric ontology project {self._ttl_esc(version.project_id)}" .',
            "",
        ]
        class_local: Dict[str, str] = {
            c.id: self._safe_local(c.normalized_name or c.name or c.id) for c in version.classes
        }
        for c in version.classes:
            local = class_local[c.id]
            lines.append(f"weave:{local} a owl:Class ;")
            lines.append(f'  rdfs:label "{self._ttl_esc(c.name or c.normalized_name)}" ;')
            if c.definition:
                lines.append(f'  rdfs:comment "{self._ttl_esc(c.definition)}" ;')
            parent = class_local.get(getattr(c, "parent_class_id", None) or "")
            if parent:
                lines.append(f"  rdfs:subClassOf weave:{parent} ;")
            for alias in (c.aliases or [])[:8]:
                if alias and alias != c.name:
                    lines.append(f'  rdfs:label "{self._ttl_esc(alias)}" ;')
            lines.append(f'  weave:confidence "{c.confidence_score:.4f}"^^xsd:decimal ;')
            lines.append(f'  weave:status "{self._ttl_esc(getattr(c.status, "value", str(c.status)))}" .')
            lines.append("")

        used_preds: Dict[str, int] = {}
        for r in version.relationships:
            base_pred = self._safe_local(r.relationship_name or r.id)
            n = used_preds.get(base_pred, 0)
            used_preds[base_pred] = n + 1
            pred = base_pred if n == 0 else f"{base_pred}_{n + 1}"
            src = class_local.get(r.source_class_id) or self._safe_local(r.source_class_id)
            tgt = class_local.get(r.target_class_id) or self._safe_local(r.target_class_id)
            prop_types = ["owl:ObjectProperty"]
            card = (r.cardinality_if_detected or "").lower()
            if card in ("1:1", "1-1", "one-to-one"):
                prop_types.extend(["owl:FunctionalProperty", "owl:InverseFunctionalProperty"])
            elif card.startswith("1:") or card in ("1:n", "1-n", "one-to-many"):
                prop_types.append("owl:FunctionalProperty")
            lines.append(f"weave:{pred} a {', '.join(prop_types)} ;")
            lines.append(f'  rdfs:label "{self._ttl_esc(r.relationship_name)}" ;')
            if r.definition:
                lines.append(f'  rdfs:comment "{self._ttl_esc(r.definition)}" ;')
            lines.append(f"  rdfs:domain weave:{src} ;")
            lines.append(f"  rdfs:range weave:{tgt} ;")
            if r.cardinality_if_detected:
                lines.append(f'  weave:cardinality "{self._ttl_esc(r.cardinality_if_detected)}" ;')
            lines.append(f'  weave:confidence "{r.confidence_score:.4f}"^^xsd:decimal .')
            lines.append("")

        for a in version.attributes:
            local = self._safe_local(
                f"{class_local.get(a.class_id, a.class_id)}_{a.attribute_name or a.normalized_name or a.id}"
            )
            domain = class_local.get(a.class_id) or self._safe_local(a.class_id)
            xsd_t = self._xsd_type(a.data_type_guess)
            lines.append(f"weave:{local} a owl:DatatypeProperty ;")
            lines.append(f'  rdfs:label "{self._ttl_esc(a.attribute_name or a.normalized_name)}" ;')
            if a.description:
                lines.append(f'  rdfs:comment "{self._ttl_esc(a.description)}" ;')
            lines.append(f"  rdfs:domain weave:{domain} ;")
            lines.append(f"  rdfs:range {xsd_t} ;")
            if a.required_flag_guess:
                lines.append('  weave:required "true"^^xsd:boolean ;')
            lines.append(f'  weave:confidence "{a.confidence_score:.4f}"^^xsd:decimal .')
            lines.append("")

        for c in version.constraints:
            local = self._safe_local(f"constraint_{c.id}")
            lines.append(f"weave:{local} a owl:Axiom ;")
            lines.append(f'  rdfs:label "{self._ttl_esc(getattr(c.constraint_type, "value", str(c.constraint_type)))}" ;')
            lines.append(f'  rdfs:comment "{self._ttl_esc(c.expression)}" .')
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def export_shacl(self, version: OntologyVersion) -> str:
        """Measured rules as SHACL shapes.

        Each class becomes a NodeShape. Required attributes become
        ``sh:minCount 1``. Cardinality on a relationship becomes ``sh:maxCount``
        / ``sh:minCount`` on a property shape. Business-rule constraints are
        kept as ``sh:description`` so a reviewer can see the original wording.
        """
        base = f"{WEAVE_ONT_NS}{version.project_id}/"
        lines = [
            "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            "@prefix sh: <http://www.w3.org/ns/shacl#> .",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            f"@prefix weave: <{base}> .",
            "",
        ]
        class_local = {
            c.id: self._safe_local(c.normalized_name or c.name or c.id) for c in version.classes
        }
        attrs_by_class: Dict[str, List[OntologyAttribute]] = {}
        for a in version.attributes:
            attrs_by_class.setdefault(a.class_id, []).append(a)
        rels_by_source: Dict[str, List[OntologyRelationship]] = {}
        for r in version.relationships:
            rels_by_source.setdefault(r.source_class_id, []).append(r)
        constraints_by_class: Dict[str, List[OntologyConstraint]] = {}
        for c in version.constraints:
            if c.related_class_id:
                constraints_by_class.setdefault(c.related_class_id, []).append(c)

        used_preds: Dict[str, int] = {}
        for cls in version.classes:
            local = class_local[cls.id]
            shape = f"{local}Shape"
            lines.append(f"weave:{shape} a sh:NodeShape ;")
            lines.append(f"  sh:targetClass weave:{local} ;")
            lines.append(f'  sh:name "{self._ttl_esc(cls.name or cls.normalized_name)}" ;')
            for a in attrs_by_class.get(cls.id) or []:
                prop = self._safe_local(f"{local}_{a.attribute_name or a.normalized_name or a.id}")
                lines.append("  sh:property [")
                lines.append(f"    sh:path weave:{prop} ;")
                lines.append(f"    sh:datatype {self._xsd_type(a.data_type_guess)} ;")
                if a.required_flag_guess:
                    lines.append("    sh:minCount 1 ;")
                lines.append(f'    sh:name "{self._ttl_esc(a.attribute_name or a.normalized_name)}" ;')
                lines.append("  ] ;")
            for r in rels_by_source.get(cls.id) or []:
                base_pred = self._safe_local(r.relationship_name or r.id)
                n = used_preds.get(base_pred, 0)
                used_preds[base_pred] = n + 1
                pred = base_pred if n == 0 else f"{base_pred}_{n + 1}"
                tgt = class_local.get(r.target_class_id) or self._safe_local(r.target_class_id)
                lines.append("  sh:property [")
                lines.append(f"    sh:path weave:{pred} ;")
                lines.append(f"    sh:class weave:{tgt} ;")
                card = (r.cardinality_if_detected or "").lower()
                if card in ("1:1", "1-1", "one-to-one", "n:1", "n-1", "many-to-one"):
                    lines.append("    sh:maxCount 1 ;")
                if card in ("1:1", "1-1", "one-to-one", "1:n", "1-n", "one-to-many"):
                    lines.append("    sh:minCount 1 ;")
                lines.append(f'    sh:name "{self._ttl_esc(r.relationship_name)}" ;')
                lines.append("  ] ;")
            for rule in constraints_by_class.get(cls.id) or []:
                lines.append(f'  sh:description "{self._ttl_esc(rule.expression)}" ;')
            # Close the shape: last property ends with `;`, replace trailing with `.`
            if lines[-1].endswith(" ;"):
                lines[-1] = lines[-1][:-2] + " ."
            else:
                lines.append("  .")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

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
            "parent_class_id": c.parent_class_id,
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

    def _safe_local(self, name: str) -> str:
        raw = (name or "thing").strip()
        safe = re.sub(r"[^A-Za-z0-9_\-]+", "_", raw)
        safe = re.sub(r"_+", "_", safe).strip("_")
        if not safe:
            safe = "thing"
        if safe[0].isdigit():
            safe = f"n_{safe}"
        return safe

    def _ttl_esc(self, value: Optional[str]) -> str:
        text = (value or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")
        return text[:2000]

    def _xsd_type(self, data_type_guess: Optional[str]) -> str:
        t = (data_type_guess or "string").strip().lower()
        mapping = {
            "string": "xsd:string",
            "str": "xsd:string",
            "text": "xsd:string",
            "varchar": "xsd:string",
            "int": "xsd:integer",
            "integer": "xsd:integer",
            "bigint": "xsd:long",
            "long": "xsd:long",
            "float": "xsd:float",
            "double": "xsd:double",
            "decimal": "xsd:decimal",
            "number": "xsd:decimal",
            "bool": "xsd:boolean",
            "boolean": "xsd:boolean",
            "date": "xsd:date",
            "datetime": "xsd:dateTime",
            "timestamp": "xsd:dateTime",
        }
        for key, xsd in mapping.items():
            if key in t:
                return xsd
        return "xsd:string"
