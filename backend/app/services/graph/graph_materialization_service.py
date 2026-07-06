"""Materialize canonical knowledge graph from approved ontology."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.models.ontology import OntologyElementStatus
from app.services.graph.graph_store import graph_store
from app.services.ontology.ontology_db_repository import ontology_db_repository
from app.services.platform.fabric_store import fabric_store

logger = logging.getLogger(__name__)


class GraphMaterializationService:
    def materialize(
        self,
        fabric_id: str,
        ontology_version_id: str,
        storage_backend: Optional[str] = None,
    ) -> Dict[str, Any]:
        backend = (storage_backend or settings.GRAPH_STORAGE_BACKEND or "postgres").lower()
        version = ontology_db_repository.get_version(ontology_version_id)
        if not version:
            raise ValueError(f"Ontology version not found: {ontology_version_id}")

        approved_classes = [
            c for c in version.classes
            if c.status in (OntologyElementStatus.APPROVED, OntologyElementStatus.DRAFT, OntologyElementStatus.REVIEWED)
        ]
        approved_rels = [
            r for r in version.relationships
            if r.status not in (OntologyElementStatus.REJECTED,)
            and r.source_class_id and r.target_class_id
        ]

        class_to_node: Dict[str, str] = {}
        nodes: List[Dict[str, Any]] = []
        for c in approved_classes:
            node_id = f"gn_{uuid.uuid4().hex[:12]}"
            class_to_node[c.id] = node_id
            props = {}
            source_table = None
            for a in version.attributes:
                if a.class_id == c.id:
                    props[a.attribute_name] = a.data_type_guess or "string"
            nodes.append({
                "id": node_id,
                "ontology_class_id": c.id,
                "label": c.name,
                "normalized_name": c.normalized_name,
                "properties": props,
                "source_table": source_table,
            })

        edges: List[Dict[str, Any]] = []
        for r in approved_rels:
            src = class_to_node.get(r.source_class_id)
            tgt = class_to_node.get(r.target_class_id)
            if not src or not tgt:
                continue
            edges.append({
                "id": f"ge_{uuid.uuid4().hex[:12]}",
                "source_node_id": src,
                "target_node_id": tgt,
                "relationship_type": r.relationship_name,
                "confidence": r.confidence_score,
                "evidence_refs": [
                    {"snippet": (ev.text_snippet or "")[:200]}
                    for ev in (r.evidence or [])[:3]
                ],
            })

        graph_store.clear_fabric_version(fabric_id, ontology_version_id)
        counts = graph_store.insert_graph(fabric_id, ontology_version_id, nodes, edges)
        export_uris: Dict[str, Any] = {}

        if backend in ("neo4j", "all"):
            from app.services.graph.adapters.neo4j_adapter import neo4j_adapter
            export_uris["neo4j"] = neo4j_adapter.export_fabric_graph(fabric_id, ontology_version_id)

        if backend in ("rdf", "stardog", "all"):
            from app.services.graph.adapters.rdf_adapter import rdf_adapter
            export_uris["rdf"] = rdf_adapter.export_fabric_graph(fabric_id, ontology_version_id)
            if backend == "stardog" and settings.STARDOG_ENDPOINT:
                export_uris["stardog"] = rdf_adapter.push_to_stardog(fabric_id, ontology_version_id)

        run_id = graph_store.record_build_run(
            fabric_id=fabric_id,
            ontology_version_id=ontology_version_id,
            status="ready",
            node_count=counts["node_count"],
            edge_count=counts["edge_count"],
            storage_backend=backend,
            export_uris=export_uris,
        )

        fabric = fabric_store.get(fabric_id)
        if fabric:
            fabric["approved_ontology_version_id"] = ontology_version_id
            fabric_store.save(fabric)

        return {
            "build_run_id": run_id,
            "fabric_id": fabric_id,
            "ontology_version_id": ontology_version_id,
            "node_count": counts["node_count"],
            "edge_count": counts["edge_count"],
            "storage_backend": backend,
            "export_uris": export_uris,
        }


graph_materialization_service = GraphMaterializationService()
