"""Architecture / migration blueprint and risk scoring."""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.llm.llm_router import llm_router

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def detect_cycles(graph: Dict[str, Any]) -> List[List[str]]:
    adj: Dict[str, List[str]] = defaultdict(list)
    for e in graph.get("edges") or []:
        if e.get("type") in ("depends_on", "imports"):
            adj[e["source"]].append(e["target"])

    cycles: List[List[str]] = []
    visiting: Set[str] = set()
    visited: Set[str] = set()
    stack: List[str] = []

    def dfs(node: str) -> None:
        if node in visiting:
            if node in stack:
                idx = stack.index(node)
                cycles.append(stack[idx:] + [node])
            return
        if node in visited:
            return
        visiting.add(node)
        stack.append(node)
        for nxt in adj.get(node, []):
            dfs(nxt)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for n in list(adj.keys())[:200]:
        dfs(n)
        if len(cycles) >= 15:
            break
    return cycles


def coupling_hotspots(graph: Dict[str, Any], limit: int = 15) -> List[Dict[str, Any]]:
    degree: Dict[str, int] = defaultdict(int)
    for e in graph.get("edges") or []:
        if e.get("type") in ("depends_on", "imports", "integrates_with"):
            degree[e["source"]] += 1
            degree[e["target"]] += 1
    ranked = sorted(degree.items(), key=lambda x: -x[1])[:limit]
    labels = {n["id"]: n.get("label") for n in graph.get("nodes") or []}
    return [{"id": nid, "label": labels.get(nid, nid), "degree": deg} for nid, deg in ranked]


def build_blueprint(
    *,
    inventory: Dict[str, Any],
    graph: Dict[str, Any],
    enrichment: Dict[str, Any],
    migration_goal: Optional[str] = None,
) -> Dict[str, Any]:
    cycles = detect_cycles(graph)
    hotspots = coupling_hotspots(graph)
    risks: List[Dict[str, Any]] = []
    for cyc in cycles[:10]:
        risks.append(
            {
                "id": f"risk_cycle_{len(risks)+1}",
                "severity": "high",
                "type": "circular_dependency",
                "message": "Circular dependency detected",
                "nodes": cyc[:12],
            }
        )
    for hs in hotspots[:8]:
        if hs["degree"] >= 8:
            risks.append(
                {
                    "id": f"risk_hotspot_{hs['id']}",
                    "severity": "medium",
                    "type": "high_coupling",
                    "message": f"High coupling around {hs['label']}",
                    "nodes": [hs["id"]],
                    "degree": hs["degree"],
                }
            )

    modules = [m.get("name") for m in (inventory.get("modules") or []) if m.get("name")]
    # Heuristic waves: entrypoints / api-ish first, then core, then leaf
    summaries = {str(s.get("name")): s for s in (enrichment.get("module_summaries") or []) if isinstance(s, dict)}
    wave1, wave2, wave3 = [], [], []
    for name in modules:
        layer = str((summaries.get(name) or {}).get("layer") or "").lower()
        if any(k in layer for k in ("api", "ui", "web", "gateway", "controller")):
            wave1.append(name)
        elif any(k in layer for k in ("domain", "core", "service", "business")):
            wave2.append(name)
        else:
            wave3.append(name)
    if not wave1 and not wave2:
        # split by size
        mid = max(1, len(modules) // 3)
        wave1, wave2, wave3 = modules[:mid], modules[mid : mid * 2], modules[mid * 2 :]

    waves = [
        {"name": "Wave 1 — Edge / API / UI", "modules": wave1, "intent": "Stabilize external contracts first"},
        {"name": "Wave 2 — Domain / Services", "modules": wave2, "intent": "Migrate core business logic"},
        {"name": "Wave 3 — Shared / Data / Leaf", "modules": wave3, "intent": "Move shared libs and data adapters"},
    ]

    bounded = []
    for concept in enrichment.get("domain_concepts") or []:
        if isinstance(concept, dict) and concept.get("name"):
            bounded.append(
                {
                    "name": concept["name"],
                    "modules": concept.get("related_modules") or [],
                    "description": concept.get("description"),
                }
            )

    llm_extra = _llm_blueprint_refine(inventory, enrichment, migration_goal, waves, risks)
    if llm_extra:
        if isinstance(llm_extra.get("waves"), list) and llm_extra["waves"]:
            waves = llm_extra["waves"]
        if isinstance(llm_extra.get("bounded_contexts"), list) and llm_extra["bounded_contexts"]:
            bounded = llm_extra["bounded_contexts"]
        if isinstance(llm_extra.get("additional_risks"), list):
            risks.extend(llm_extra["additional_risks"][:10])
        narrative = llm_extra.get("narrative")
    else:
        narrative = None

    # Add risk + slice nodes into a copy for optional graph merge
    graph_additions = {"nodes": [], "edges": []}
    for i, wave in enumerate(waves):
        sid = f"slice:wave_{i+1}"
        graph_additions["nodes"].append(
            {"id": sid, "type": "migration_slice", "label": wave.get("name") or sid, "properties": wave}
        )
        for mod in wave.get("modules") or []:
            # Prefer top-level module folder names; LLM may emit file paths.
            mod_name = str(mod).strip()
            if "/" in mod_name or mod_name.endswith((".py", ".ts", ".js", ".java")):
                mod_name = mod_name.split("/", 1)[0].rsplit(".", 1)[0]
            if not mod_name:
                continue
            graph_additions["edges"].append(
                {"source": sid, "target": f"module:{mod_name}", "type": "maps_to", "properties": {}}
            )
    for risk in risks[:20]:
        rid = risk.get("id") or f"risk:{len(graph_additions['nodes'])}"
        graph_additions["nodes"].append(
            {
                "id": rid if str(rid).startswith("risk:") else f"risk:{rid}",
                "type": "risk",
                "label": risk.get("message") or rid,
                "properties": risk,
            }
        )
        for nid in risk.get("nodes") or []:
            graph_additions["edges"].append(
                {
                    "source": rid if str(rid).startswith("risk:") else f"risk:{rid}",
                    "target": nid if ":" in str(nid) else f"module:{nid}",
                    "type": "blocked_by",
                    "properties": {},
                }
            )

    return {
        "waves": waves,
        "bounded_contexts": bounded,
        "risks": risks,
        "hotspots": hotspots,
        "cycles": cycles[:15],
        "narrative": narrative
        or (
            f"Proposed {len(waves)} migration waves across {len(modules)} modules "
            f"with {len(risks)} identified risks."
        ),
        "migration_goal": migration_goal,
        "graph_additions": graph_additions,
    }


def _llm_blueprint_refine(
    inventory: Dict[str, Any],
    enrichment: Dict[str, Any],
    migration_goal: Optional[str],
    waves: List[Dict[str, Any]],
    risks: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    prompt = f"""Refine a migration blueprint. Return ONLY JSON with keys:
waves (array of {{name, modules, intent}}),
bounded_contexts (array of {{name, modules, description}}),
additional_risks (array of {{severity, type, message, nodes}}),
narrative (string).

Goal: {migration_goal or 'modernization'}
Languages: {json.dumps(inventory.get('languages') or {})}
Frameworks: {json.dumps(inventory.get('frameworks') or [])}
Current waves: {json.dumps(waves)[:3000]}
Known risks: {json.dumps(risks[:8])[:2000]}
Domain concepts: {json.dumps((enrichment.get('domain_concepts') or [])[:15])[:2000]}
"""
    try:
        raw = llm_router.chat_completion(
            messages=[
                {"role": "system", "content": "Respond with compact JSON only."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1400,
            temperature=0.2,
        )
        return _extract_json(raw)
    except Exception as exc:
        logger.warning("Blueprint LLM refine failed: %s", exc)
        return None


def apply_graph_additions(graph: Dict[str, Any], additions: Dict[str, Any]) -> Dict[str, Any]:
    """Merge blueprint nodes/edges, dropping edges whose endpoints are missing."""
    nodes = {n["id"]: n for n in graph.get("nodes") or [] if n.get("id")}
    edges = list(graph.get("edges") or [])
    keys = {f"{e.get('source')}|{e.get('type')}|{e.get('target')}" for e in edges}

    for n in additions.get("nodes") or []:
        nid = n.get("id")
        if nid:
            nodes[nid] = n

    # Map loose module names / file paths onto existing module:* nodes when possible.
    module_by_label = {
        str(n.get("label") or "").lower(): nid
        for nid, n in nodes.items()
        if n.get("type") == "module"
    }
    module_ids = {nid for nid, n in nodes.items() if n.get("type") == "module"}

    def _resolve_endpoint(raw: Any) -> Optional[str]:
        if raw is None:
            return None
        text = str(raw).strip()
        if not text:
            return None
        if text in nodes:
            return text
        # LLM sometimes emits file paths as modules: app/main.py → module:app
        if text.startswith("module:"):
            rest = text[len("module:") :]
            if rest in nodes:
                return rest
            if text in module_ids:
                return text
            top = rest.split("/", 1)[0].split(".", 1)[0]
            candidate = f"module:{top}"
            if candidate in nodes:
                return candidate
            label_hit = module_by_label.get(top.lower()) or module_by_label.get(rest.lower())
            if label_hit:
                return label_hit
            return None
        # bare name
        candidate = f"module:{text}"
        if candidate in nodes:
            return candidate
        top = text.split("/", 1)[0].split(".", 1)[0]
        candidate = f"module:{top}"
        if candidate in nodes:
            return candidate
        return module_by_label.get(text.lower()) or module_by_label.get(top.lower())

    for e in additions.get("edges") or []:
        source = _resolve_endpoint(e.get("source"))
        target = _resolve_endpoint(e.get("target"))
        if not source or not target:
            continue
        if source not in nodes or target not in nodes:
            continue
        etype = e.get("type") or "related"
        key = f"{source}|{etype}|{target}"
        if key in keys:
            continue
        keys.add(key)
        edges.append({**e, "source": source, "target": target, "type": etype})

    return {**graph, "nodes": list(nodes.values()), "edges": edges}
