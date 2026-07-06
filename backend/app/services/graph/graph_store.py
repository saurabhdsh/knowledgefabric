"""Canonical graph storage and traversal (Postgres v1)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from app.db.models import GraphBuildRunRecord, GraphEdgeRecord, GraphNodeRecord
from app.db.session import db_session, get_session_factory

logger = logging.getLogger(__name__)


class GraphStore:
    def clear_fabric_version(self, fabric_id: str, ontology_version_id: str) -> None:
        with db_session() as session:
            node_ids = [
                n.id
                for n in session.query(GraphNodeRecord)
                .filter(
                    GraphNodeRecord.fabric_id == fabric_id,
                    GraphNodeRecord.ontology_version_id == ontology_version_id,
                )
                .all()
            ]
            if node_ids:
                session.query(GraphEdgeRecord).filter(
                    GraphEdgeRecord.fabric_id == fabric_id,
                    GraphEdgeRecord.ontology_version_id == ontology_version_id,
                ).delete(synchronize_session=False)
                session.query(GraphNodeRecord).filter(GraphNodeRecord.id.in_(node_ids)).delete(
                    synchronize_session=False
                )

    def insert_graph(
        self,
        fabric_id: str,
        ontology_version_id: str,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        with db_session() as session:
            for n in nodes:
                session.add(
                    GraphNodeRecord(
                        id=n["id"],
                        fabric_id=fabric_id,
                        ontology_class_id=n.get("ontology_class_id"),
                        ontology_version_id=ontology_version_id,
                        label=n["label"],
                        normalized_name=n["normalized_name"],
                        properties=n.get("properties") or {},
                        source_table=n.get("source_table"),
                        source_column=n.get("source_column"),
                    )
                )
            for e in edges:
                session.add(
                    GraphEdgeRecord(
                        id=e["id"],
                        fabric_id=fabric_id,
                        source_node_id=e["source_node_id"],
                        target_node_id=e["target_node_id"],
                        relationship_type=e["relationship_type"],
                        ontology_version_id=ontology_version_id,
                        properties=e.get("properties") or {},
                        confidence=float(e.get("confidence", 1.0)),
                        evidence_refs=e.get("evidence_refs") or [],
                    )
                )
        return {"node_count": len(nodes), "edge_count": len(edges)}

    def record_build_run(
        self,
        fabric_id: str,
        ontology_version_id: str,
        status: str,
        node_count: int,
        edge_count: int,
        storage_backend: str = "postgres",
        export_uris: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> str:
        run_id = f"gbr_{uuid.uuid4().hex[:12]}"
        with db_session() as session:
            session.add(
                GraphBuildRunRecord(
                    id=run_id,
                    fabric_id=fabric_id,
                    ontology_version_id=ontology_version_id,
                    status=status,
                    storage_backend=storage_backend,
                    node_count=node_count,
                    edge_count=edge_count,
                    export_uris=export_uris or {},
                    error_message=error_message,
                    built_at=datetime.utcnow() if status == "ready" else None,
                )
            )
        return run_id

    def get_graph_payload(
        self,
        fabric_id: str,
        ontology_version_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        session = get_session_factory()()
        try:
            node_q = session.query(GraphNodeRecord).filter(GraphNodeRecord.fabric_id == fabric_id)
            if ontology_version_id:
                node_q = node_q.filter(GraphNodeRecord.ontology_version_id == ontology_version_id)
            nodes = node_q.all()
            if not nodes:
                return {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0}

            version_id = ontology_version_id or nodes[0].ontology_version_id
            edges = (
                session.query(GraphEdgeRecord)
                .filter(
                    GraphEdgeRecord.fabric_id == fabric_id,
                    GraphEdgeRecord.ontology_version_id == version_id,
                )
                .all()
            )
            return {
                "fabric_id": fabric_id,
                "ontology_version_id": version_id,
                "nodes": [
                    {
                        "id": n.id,
                        "label": n.label,
                        "normalized_name": n.normalized_name,
                        "ontology_class_id": n.ontology_class_id,
                        "properties": n.properties,
                        "source_table": n.source_table,
                    }
                    for n in nodes
                ],
                "edges": [
                    {
                        "id": e.id,
                        "source": e.source_node_id,
                        "target": e.target_node_id,
                        "relationship_type": e.relationship_type,
                        "confidence": e.confidence,
                        "evidence_refs": e.evidence_refs,
                    }
                    for e in edges
                ],
                "node_count": len(nodes),
                "edge_count": len(edges),
            }
        finally:
            session.close()

    def get_neighbors(
        self,
        fabric_id: str,
        node_id: str,
        hops: int = 1,
        ontology_version_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        hops = max(1, min(hops, 3))
        session = get_session_factory()()
        try:
            visited: Set[str] = {node_id}
            frontier: Set[str] = {node_id}
            all_edges: List[GraphEdgeRecord] = []
            for _ in range(hops):
                if not frontier:
                    break
                q = session.query(GraphEdgeRecord).filter(
                    GraphEdgeRecord.fabric_id == fabric_id,
                    GraphEdgeRecord.source_node_id.in_(list(frontier)),
                )
                if ontology_version_id:
                    q = q.filter(GraphEdgeRecord.ontology_version_id == ontology_version_id)
                edges = q.all()
                all_edges.extend(edges)
                next_frontier: Set[str] = set()
                for e in edges:
                    if e.target_node_id not in visited:
                        next_frontier.add(e.target_node_id)
                        visited.add(e.target_node_id)
                frontier = next_frontier

            node_recs = (
                session.query(GraphNodeRecord)
                .filter(GraphNodeRecord.id.in_(list(visited)))
                .all()
            )
            return {
                "root_node_id": node_id,
                "hops": hops,
                "nodes": [
                    {"id": n.id, "label": n.label, "normalized_name": n.normalized_name}
                    for n in node_recs
                ],
                "edges": [
                    {
                        "id": e.id,
                        "source": e.source_node_id,
                        "target": e.target_node_id,
                        "relationship_type": e.relationship_type,
                    }
                    for e in all_edges
                ],
            }
        finally:
            session.close()

    def find_nodes_by_label(
        self,
        fabric_id: str,
        query: str,
        ontology_version_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        q_lower = query.lower()
        session = get_session_factory()()
        try:
            node_q = session.query(GraphNodeRecord).filter(GraphNodeRecord.fabric_id == fabric_id)
            if ontology_version_id:
                node_q = node_q.filter(GraphNodeRecord.ontology_version_id == ontology_version_id)
            matches = []
            for n in node_q.all():
                if q_lower in n.label.lower() or q_lower in n.normalized_name.lower():
                    matches.append({
                        "id": n.id,
                        "label": n.label,
                        "normalized_name": n.normalized_name,
                    })
                if len(matches) >= limit:
                    break
            return matches
        finally:
            session.close()


graph_store = GraphStore()
