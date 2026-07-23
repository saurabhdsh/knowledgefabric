"""Graph-augmented retrieval orchestrator (Phase 4)."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.graph.graph_store import graph_store
from app.services.platform.fabric_store import fabric_store
from app.services.vector_service import vector_service

logger = logging.getLogger(__name__)


class RetrievalOrchestrator:
    def retrieve(
        self,
        fabric_id: str,
        query: str,
        top_k: int = 5,
        graph_hops: int = 1,
        use_graph: Optional[bool] = None,
        retrieve_all: bool = False,
    ) -> Dict[str, Any]:
        fabric = fabric_store.get(fabric_id)
        if not fabric:
            raise ValueError("Fabric not found")

        if retrieve_all or top_k is None or int(top_k) <= 0:
            # Full-fabric retrieval for Test LLM / comprehensive answers.
            top_k = 0
        else:
            # Keep a sane upper bound for partner retrieve API defaults only when
            # callers pass an explicit positive top_k without retrieve_all.
            top_k = max(1, int(top_k))

        graph_enabled = use_graph if use_graph is not None else settings.USE_GRAPH_RETRIEVAL
        version_id = fabric.get("approved_ontology_version_id")

        trace: List[Dict[str, Any]] = []
        chunks = vector_service.search_similar_chunks(query, fabric_id, top_k=top_k)
        trace.append({
            "stage": "vector_search",
            "count": len(chunks),
            "retrieve_all": bool(retrieve_all or top_k <= 0),
            "requested_top_k": top_k,
        })

        graph_context: Dict[str, Any] = {"nodes": [], "edges": [], "paths": []}
        entities: List[Dict[str, Any]] = []

        if graph_enabled and version_id:
            linked = self._link_entities(fabric_id, query, version_id)
            entities = linked
            trace.append({"stage": "entity_linking", "count": len(linked)})
            for node in linked[:3]:
                expansion = graph_store.get_neighbors(
                    fabric_id, node["id"], hops=graph_hops, ontology_version_id=version_id
                )
                graph_context["nodes"].extend(expansion.get("nodes") or [])
                graph_context["edges"].extend(expansion.get("edges") or [])
                graph_context["paths"].append({
                    "root": node["id"],
                    "hops": graph_hops,
                    "edge_count": len(expansion.get("edges") or []),
                })
            trace.append({
                "stage": "graph_expansion",
                "nodes": len(graph_context["nodes"]),
                "edges": len(graph_context["edges"]),
            })
        elif graph_enabled and not version_id:
            trace.append({"stage": "graph_expansion", "skipped": "no approved ontology version"})

        merged_chunks = self._merge_context(chunks, graph_context, entities)
        ontology_summary = self._ontology_summary(fabric)

        return {
            "fabric_id": fabric_id,
            "fabric_name": fabric.get("name"),
            "query": query,
            "top_k": top_k,
            "chunks": merged_chunks,
            "graph_context": graph_context,
            "entities": entities,
            "ontology_version_id": version_id,
            "ontology_summary": ontology_summary,
            "retrieval_trace": trace,
            "graph_retrieval_enabled": graph_enabled,
        }

    def build_query_context(self, fabric_id: str, retrieval: Dict[str, Any]) -> str:
        parts = []
        summary = retrieval.get("ontology_summary")
        if summary:
            parts.append(f"Domain ontology (approved): {summary}")
        for path in retrieval.get("graph_context", {}).get("paths") or []:
            parts.append(f"Graph path from {path.get('root')}: {path.get('edge_count')} related edges")
        for ent in retrieval.get("entities") or []:
            parts.append(f"Linked entity: {ent.get('label')} ({ent.get('normalized_name')})")
        return "\n".join(parts)

    def _link_entities(
        self,
        fabric_id: str,
        query: str,
        version_id: str,
    ) -> List[Dict[str, Any]]:
        tokens = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
        found: Dict[str, Dict[str, Any]] = {}
        for token in tokens[:8]:
            for node in graph_store.find_nodes_by_label(fabric_id, token, version_id, limit=5):
                found[node["id"]] = node
        if not found:
            for node in graph_store.find_nodes_by_label(fabric_id, query, version_id, limit=5):
                found[node["id"]] = node
        return list(found.values())

    def _merge_context(
        self,
        chunks: List[Dict[str, Any]],
        graph_context: Dict[str, Any],
        entities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not graph_context.get("nodes"):
            return chunks
        graph_summary = {
            "rank": 0,
            "content": self._graph_summary_text(graph_context, entities),
            "similarity_score": 0.0,
            "metadata": {"source": "graph_context", "type": "graph_expansion"},
        }
        return [graph_summary] + chunks

    def _graph_summary_text(
        self,
        graph_context: Dict[str, Any],
        entities: List[Dict[str, Any]],
    ) -> str:
        lines = ["Related knowledge graph context:"]
        for ent in entities:
            lines.append(f"- Entity: {ent.get('label')}")
        for edge in graph_context.get("edges") or []:
            lines.append(f"- Relationship: {edge.get('relationship_type')}")
        return "\n".join(lines)

    def _ontology_summary(self, fabric: Dict[str, Any]) -> Optional[str]:
        version_id = fabric.get("approved_ontology_version_id")
        if not version_id:
            return None
        from app.services.ontology.ontology_db_repository import ontology_db_repository
        version = ontology_db_repository.get_version(version_id)
        if not version:
            return None
        class_names = [c.name for c in version.classes[:12]]
        rel_names = [r.relationship_name for r in version.relationships[:8]]
        return f"Entities: {', '.join(class_names)}. Relationships: {', '.join(rel_names)}."


retrieval_orchestrator = RetrievalOrchestrator()
