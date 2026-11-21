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
        node_ids = {str(n["id"]) for n in nodes if n.get("id")}
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
            # autoflush is off — nodes must hit the table before edge FKs validate.
            session.flush()
            kept_edges = 0
            for e in edges:
                src = str(e.get("source_node_id") or "")
                tgt = str(e.get("target_node_id") or "")
                # Drop missing endpoints and accidental self-loops (FK-style
                # "references_X" often points a class at itself when source/target
                # class ids were resolved incorrectly).
                if src not in node_ids or tgt not in node_ids or src == tgt:
                    continue
                session.add(
                    GraphEdgeRecord(
                        id=e["id"],
                        fabric_id=fabric_id,
                        source_node_id=src,
                        target_node_id=tgt,
                        relationship_type=e["relationship_type"],
                        ontology_version_id=ontology_version_id,
                        properties=e.get("properties") or {},
                        confidence=float(e.get("confidence", 1.0)),
                        evidence_refs=e.get("evidence_refs") or [],
                    )
                )
                kept_edges += 1
        return {"node_count": len(nodes), "edge_count": kept_edges}

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
                        "properties": e.properties or {},
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
        """Undirected BFS over stored edges (outgoing and incoming)."""
        hops = max(1, min(hops, 3))
        session = get_session_factory()()
        try:
            visited: Set[str] = {node_id}
            frontier: Set[str] = {node_id}
            all_edges: List[GraphEdgeRecord] = []
            seen_edge_ids: Set[str] = set()
            for _ in range(hops):
                if not frontier:
                    break
                frontier_list = list(frontier)
                q_out = session.query(GraphEdgeRecord).filter(
                    GraphEdgeRecord.fabric_id == fabric_id,
                    GraphEdgeRecord.source_node_id.in_(frontier_list),
                )
                q_in = session.query(GraphEdgeRecord).filter(
                    GraphEdgeRecord.fabric_id == fabric_id,
                    GraphEdgeRecord.target_node_id.in_(frontier_list),
                )
                if ontology_version_id:
                    q_out = q_out.filter(GraphEdgeRecord.ontology_version_id == ontology_version_id)
                    q_in = q_in.filter(GraphEdgeRecord.ontology_version_id == ontology_version_id)
                edges = q_out.all() + q_in.all()
                next_frontier: Set[str] = set()
                for e in edges:
                    if e.id in seen_edge_ids:
                        continue
                    seen_edge_ids.add(e.id)
                    all_edges.append(e)
                    for endpoint in (e.source_node_id, e.target_node_id):
                        if endpoint not in visited:
                            next_frontier.add(endpoint)
                            visited.add(endpoint)
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
                    {
                        "id": n.id,
                        "label": n.label,
                        "normalized_name": n.normalized_name,
                        "properties": n.properties or {},
                        "source_table": n.source_table,
                    }
                    for n in node_recs
                ],
                "edges": [
                    {
                        "id": e.id,
                        "source": e.source_node_id,
                        "target": e.target_node_id,
                        "relationship_type": e.relationship_type,
                        "confidence": e.confidence,
                        "evidence_refs": e.evidence_refs,
                        "properties": e.properties or {},
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
                        "properties": n.properties or {},
                        "source_table": n.source_table,
                    })
                if len(matches) >= limit:
                    break
            return matches
        finally:
            session.close()


graph_store = GraphStore()
