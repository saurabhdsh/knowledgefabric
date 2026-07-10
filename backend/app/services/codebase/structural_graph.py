"""Build typed structural code graph from workspace files."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set

from app.services.codebase import LANGUAGE_BY_EXT
from app.services.codebase.ignore import iter_source_files
from app.services.codebase.parsers import parse_file


def build_structural_graph(
    root: Path,
    inventory: Dict[str, Any],
    *,
    max_parse_files: int = 2500,
) -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    edge_keys: Set[str] = set()

    def add_node(node_id: str, ntype: str, label: str, **props: Any) -> None:
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, "type": ntype, "label": label, "properties": props}
        else:
            nodes[node_id]["properties"].update({k: v for k, v in props.items() if v is not None})

    def add_edge(source: str, target: str, etype: str, **props: Any) -> None:
        key = f"{source}|{etype}|{target}"
        if key in edge_keys:
            return
        edge_keys.add(key)
        edges.append({"source": source, "target": target, "type": etype, "properties": props})

    ws_id = "workspace:root"
    add_node(ws_id, "workspace", root.name or "workspace", path=".")

    module_files: Dict[str, List[str]] = defaultdict(list)
    import_counts: Dict[str, int] = defaultdict(int)
    contracts: List[Dict[str, Any]] = []
    data_entities: List[str] = []

    rel_files = inventory.get("all_relative_files") or []
    if not rel_files:
        rel_files = [p.relative_to(root).as_posix() for p in iter_source_files(root)]

    parsed_count = 0
    for rel in rel_files:
        if parsed_count >= max_parse_files:
            break
        path = root / rel
        if not path.is_file():
            continue
        lang = LANGUAGE_BY_EXT.get(path.suffix.lower(), "other")
        if lang == "other" and path.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".jsx", ".java"}:
            # still add file node lightly
            file_id = f"file:{rel}"
            add_node(file_id, "file", path.name, path=rel, language=lang)
            top = rel.split("/", 1)[0] if "/" in rel else "(root)"
            mod_id = f"module:{top}"
            add_node(mod_id, "module", top, path=top)
            add_edge(ws_id, mod_id, "contains")
            add_edge(mod_id, file_id, "contains")
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if len(text) > 400_000:
            text = text[:400_000]

        parsed = parse_file(path, rel, lang, text)
        parsed_count += 1

        top = rel.split("/", 1)[0] if "/" in rel else "(root)"
        mod_id = f"module:{top}"
        add_node(mod_id, "module", top, path=top)
        add_edge(ws_id, mod_id, "contains")
        module_files[top].append(rel)

        file_id = f"file:{rel}"
        add_node(file_id, "file", path.name, path=rel, language=lang)
        add_edge(mod_id, file_id, "contains")

        for sym in parsed.symbols[:40]:
            sid = f"symbol:{rel}:{sym.name}"
            add_node(sid, "symbol", sym.name, path=rel, kind=sym.kind, line=sym.line, language=lang)
            add_edge(file_id, sid, "defines")

        for imp in parsed.imports:
            if not imp or imp.startswith("."):
                # relative — map to module if possible
                continue
            import_counts[imp] += 1
            ext_id = f"external:{imp}"
            # Prefer internal module link when import matches top-level folder
            if (root / imp).exists() or any(m["name"] == imp for m in inventory.get("modules") or []):
                target = f"module:{imp}"
                add_node(target, "module", imp, path=imp)
                add_edge(file_id, target, "imports")
                add_edge(mod_id, target, "depends_on")
            else:
                add_node(ext_id, "external_system", imp, package=imp)
                add_edge(file_id, ext_id, "imports")
                add_edge(mod_id, ext_id, "integrates_with")

        for api in parsed.api_hints[:20]:
            api_id = f"api:{rel}:{api}"
            add_node(api_id, "api_endpoint", api, path=rel)
            add_edge(file_id, api_id, "exposes")
            contracts.append({"type": "api", "name": api, "path": rel})

        for ent in parsed.data_hints[:20]:
            ent_id = f"entity:{ent}"
            add_node(ent_id, "data_entity", ent, path=rel)
            add_edge(file_id, ent_id, "persists")
            data_entities.append(ent)

    # Config files
    for cfg_name in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml", ".env.example", "application.yml", "application.properties"):
        for candidate in [root / cfg_name, *root.glob(f"**/{cfg_name}")]:
            if candidate.is_file():
                try:
                    rel = candidate.relative_to(root).as_posix()
                except ValueError:
                    continue
                cid = f"config:{rel}"
                add_node(cid, "config", candidate.name, path=rel)
                add_edge(ws_id, cid, "configures")
                break

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "parsed_files": parsed_count,
            "top_imports": sorted(import_counts.items(), key=lambda x: -x[1])[:30],
        },
        "contracts": contracts[:200],
        "data_entities": sorted(set(data_entities))[:200],
        "module_files": {k: v[:100] for k, v in module_files.items()},
    }
