"""Neo4j graph export adapter (Phase 3b)."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.core.config import settings
from app.services.graph.graph_store import graph_store

logger = logging.getLogger(__name__)


class Neo4jAdapter:
    def is_configured(self) -> bool:
        return bool(settings.NEO4J_URI and settings.NEO4J_PASSWORD)

    def export_fabric_graph(
        self,
        fabric_id: str,
        ontology_version_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = graph_store.get_graph_payload(fabric_id, ontology_version_id)
        if not self.is_configured():
            return {
                "status": "skipped",
                "reason": "NEO4J_URI/NEO4J_PASSWORD not configured",
                "cypher_preview": self._cypher_preview(payload),
                "node_count": payload.get("node_count", 0),
                "edge_count": payload.get("edge_count", 0),
            }

        try:
            from neo4j import GraphDatabase
        except ImportError:
            return {
                "status": "skipped",
                "reason": "neo4j driver not installed (pip install neo4j)",
                "cypher_preview": self._cypher_preview(payload),
            }

        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER or "neo4j", settings.NEO4J_PASSWORD),
        )
        graph_key = f"{fabric_id}:{payload.get('ontology_version_id')}"
        try:
            with driver.session() as session:
                session.run(
                    "MATCH (n:WeaveNode {graph_key: $gk}) DETACH DELETE n",
                    gk=graph_key,
                )
                for n in payload.get("nodes") or []:
                    session.run(
                        """
                        CREATE (n:WeaveNode {
                            graph_key: $gk, node_id: $id, label: $label,
                            normalized_name: $norm, fabric_id: $fabric_id
                        })
                        """,
                        gk=graph_key,
                        id=n["id"],
                        label=n["label"],
                        norm=n["normalized_name"],
                        fabric_id=fabric_id,
                    )
                for e in payload.get("edges") or []:
                    session.run(
                        """
                        MATCH (a:WeaveNode {graph_key: $gk, node_id: $src})
                        MATCH (b:WeaveNode {graph_key: $gk, node_id: $tgt})
                        CREATE (a)-[r:WEAVE_REL {type: $rtype, graph_key: $gk}]->(b)
                        """,
                        gk=graph_key,
                        src=e["source"],
                        tgt=e["target"],
                        rtype=e["relationship_type"],
                    )
            return {
                "status": "exported",
                "uri": settings.NEO4J_URI,
                "graph_key": graph_key,
                "node_count": payload.get("node_count", 0),
                "edge_count": payload.get("edge_count", 0),
            }
        finally:
            driver.close()

    def _cypher_preview(self, payload: Dict[str, Any]) -> str:
        lines = ["// Weave schema graph export preview"]
        for n in payload.get("nodes") or []:
            lines.append(f"// (:Entity {{name: '{n['label']}'}})")
        for e in payload.get("edges") or []:
            lines.append(f"// ()-[:{e['relationship_type']}]->()")
        return "\n".join(lines)


neo4j_adapter = Neo4jAdapter()
