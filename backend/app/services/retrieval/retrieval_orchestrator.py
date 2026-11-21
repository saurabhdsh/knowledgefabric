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
        from app.services.retrieval.hybrid_ranker import fuse_and_rerank

        fetch_k = 0 if (retrieve_all or top_k <= 0) else max(top_k * 3, top_k)
        vector_chunks = vector_service.search_similar_chunks(query, fabric_id, top_k=fetch_k if fetch_k else 0)
        keyword_chunks: List[Dict[str, Any]] = []
        if not retrieve_all:
            from app.services.fabric_pipeline.tabular_query import _candidate_tokens

            for token in _candidate_tokens(query)[0][:4]:
                keyword_chunks.extend(vector_service.find_chunks_containing(fabric_id, token, limit=4))
            chunks = fuse_and_rerank(query, vector_chunks, keyword_chunks, top_k=max(1, top_k))
        else:
            chunks = vector_chunks
        trace.append({
            "stage": "hybrid_search",
            "vector": len(vector_chunks),
            "keyword": len(keyword_chunks),
            "kept": len(chunks),
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
        facts = retrieval.get("graph_context", {}).get("facts") or []
        if facts:
            parts.append("Graph facts:")
            parts.extend(f"- {fact}" for fact in facts[:12])
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
        facts = self.graph_facts(graph_context, entities)
        graph_context["facts"] = facts
        graph_summary = {
            "rank": 0,
            "content": "Graph facts:\n" + "\n".join(f"- {f}" for f in facts),
            "similarity_score": 0.0,
            "rerank_score": 0.9 if facts else 0.0,
            "metadata": {"source": "graph_context", "type": "graph_facts", "fact_count": len(facts)},
        }
        return [graph_summary] + chunks

    def graph_facts(
        self,
        graph_context: Dict[str, Any],
        entities: List[Dict[str, Any]],
    ) -> List[str]:
        """Turn expanded nodes/edges into readable facts (values, not type names only)."""
        by_id = {n.get("id"): n for n in (graph_context.get("nodes") or []) if n.get("id")}
        for ent in entities:
            if ent.get("id") and ent["id"] not in by_id:
                by_id[ent["id"]] = ent
        facts: List[str] = []
        for edge in graph_context.get("edges") or []:
            src = by_id.get(edge.get("source")) or {}
            tgt = by_id.get(edge.get("target")) or {}
            rel = edge.get("relationship_type") or "related_to"
            conf = edge.get("confidence")
            conf_txt = f" (confidence {float(conf):.2f})" if isinstance(conf, (int, float)) else ""
            facts.append(
                f"{self._node_fact(src)} —{rel}→ {self._node_fact(tgt)}{conf_txt}"
            )
            if len(facts) >= 16:
                break
        if not facts:
            for node in list(by_id.values())[:8]:
                facts.append(self._node_fact(node))
        return facts

    def _node_fact(self, node: Dict[str, Any]) -> str:
        if not node:
            return "unknown"
        label = node.get("label") or node.get("normalized_name") or node.get("id") or "entity"
        props = node.get("properties") or {}
        interesting = []
        for key, value in list(props.items())[:6]:
            if key in ("node_kind", "instance_id") or value in (None, "", [], {}):
                continue
            text = str(value)
            if len(text) > 80:
                text = text[:77] + "…"
            interesting.append(f"{key}={text}")
        table = node.get("source_table")
        prefix = f"{table}." if table else ""
        detail = "; ".join(interesting)
        return f"{prefix}{label}" + (f" [{detail}]" if detail else "")

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
