"""LLM enrichment for top modules (Bedrock/OpenAI via llm_router)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.services.llm.llm_router import llm_router

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def enrich_modules(
    *,
    inventory: Dict[str, Any],
    graph: Dict[str, Any],
    migration_goal: Optional[str] = None,
    max_modules: int = 12,
) -> Dict[str, Any]:
    modules = (inventory.get("modules") or [])[:max_modules]
    if not modules:
        return {
            "module_summaries": [],
            "domain_concepts": [],
            "discovery_summary": "No modules detected in workspace.",
        }

    module_lines = []
    for m in modules:
        name = m.get("name")
        files = (graph.get("module_files") or {}).get(name) or []
        module_lines.append(
            f"- {name}: {m.get('file_count', 0)} files; sample: {', '.join(files[:8])}"
        )

    languages = inventory.get("languages") or {}
    frameworks = inventory.get("frameworks") or []
    goal = migration_goal or "General modernization / migration readiness"

    prompt = f"""You are a senior software architect analyzing a codebase for knowledge-graph and migration planning.
Return ONLY valid JSON with keys:
module_summaries (array of {{name, purpose, layer, risks}}),
domain_concepts (array of {{name, description, related_modules}}),
discovery_summary (string, 2-4 paragraphs).

Languages: {json.dumps(languages)}
Frameworks: {json.dumps(frameworks)}
Migration goal: {goal}
Modules:
{chr(10).join(module_lines)}
Top imports: {json.dumps((graph.get('stats') or {}).get('top_imports') or [])}
APIs sample: {json.dumps((graph.get('contracts') or [])[:20])}
Entities sample: {json.dumps((graph.get('data_entities') or [])[:20])}
"""

    try:
        raw = llm_router.chat_completion(
            messages=[
                {"role": "system", "content": "Respond with compact JSON only. No markdown."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1800,
            temperature=0.2,
        )
        parsed = _extract_json(raw) or {}
    except Exception as exc:
        logger.warning("Codebase enrichment LLM failed: %s", exc)
        parsed = {}

    summaries = parsed.get("module_summaries") or []
    concepts = parsed.get("domain_concepts") or []
    summary = parsed.get("discovery_summary") or _fallback_summary(inventory, graph)

    # Attach domain concept nodes data for graph merge
    return {
        "module_summaries": summaries if isinstance(summaries, list) else [],
        "domain_concepts": concepts if isinstance(concepts, list) else [],
        "discovery_summary": summary if isinstance(summary, str) else str(summary),
    }


def _fallback_summary(inventory: Dict[str, Any], graph: Dict[str, Any]) -> str:
    langs = ", ".join(f"{k} ({v})" for k, v in list((inventory.get("languages") or {}).items())[:6])
    frameworks = ", ".join(inventory.get("frameworks") or []) or "unknown"
    return (
        f"Workspace contains {inventory.get('file_count', 0)} source files across languages: {langs}. "
        f"Detected frameworks/tooling: {frameworks}. "
        f"Structural graph has {(graph.get('stats') or {}).get('node_count', 0)} nodes and "
        f"{(graph.get('stats') or {}).get('edge_count', 0)} edges. "
        f"LLM enrichment was unavailable; structural analysis only."
    )


def merge_enrichment_into_graph(graph: Dict[str, Any], enrichment: Dict[str, Any]) -> Dict[str, Any]:
    nodes = {n["id"]: n for n in graph.get("nodes") or []}
    edges = list(graph.get("edges") or [])
    edge_keys = {f"{e['source']}|{e['type']}|{e['target']}" for e in edges}

    def add_edge(source: str, target: str, etype: str) -> None:
        key = f"{source}|{etype}|{target}"
        if key in edge_keys:
            return
        edge_keys.add(key)
        edges.append({"source": source, "target": target, "type": etype, "properties": {}})

    for item in enrichment.get("module_summaries") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        mid = f"module:{name}"
        if mid in nodes:
            nodes[mid].setdefault("properties", {})
            nodes[mid]["properties"]["purpose"] = item.get("purpose")
            nodes[mid]["properties"]["layer"] = item.get("layer")
            nodes[mid]["properties"]["risks"] = item.get("risks")

    for concept in enrichment.get("domain_concepts") or []:
        if not isinstance(concept, dict):
            continue
        cname = str(concept.get("name") or "").strip()
        if not cname:
            continue
        cid = f"concept:{cname}"
        nodes[cid] = {
            "id": cid,
            "type": "domain_concept",
            "label": cname,
            "properties": {"description": concept.get("description")},
        }
        for mod in concept.get("related_modules") or []:
            mid = f"module:{mod}"
            if mid in nodes:
                add_edge(cid, mid, "maps_to")

    graph = {**graph, "nodes": list(nodes.values()), "edges": edges}
    return graph
