"""Knowledge graph of a tabular Release 2.0 fabric, built from its profile.

Tables become schema nodes; relationships are the foreign keys that were
*measured* on the data (value overlap), not guessed from column names; a
bounded sample of rows is attached as instances, linked to the rows they
actually reference. The node and edge shapes match the 1.x schema graph so the
existing graph view renders it unchanged.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.fabric_pipeline.table_store import TableStore


def _humanize(name: str) -> str:
    return re.sub(r"[_\-]+", " ", str(name or "")).strip().title() or "Table"


def _col(table: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    return next((c for c in table["columns"] if c["name"] == name), None)


def _instance_id(table: str, key: Any) -> str:
    return f"instance:{table}:{re.sub(r'[^A-Za-z0-9_-]+', '_', str(key))[:80]}"


def build_profile_graph(
    fabric: Dict[str, Any],
    profile: Dict[str, Any],
    store: TableStore,
    *,
    per_table_limit: int = 20,
) -> Dict[str, Any]:
    fabric_id = str(fabric.get("id") or "")
    fabric_name = str(fabric.get("name") or fabric_id)
    tables = {t["name"]: t for t in profile["tables"]}
    nodes: List[Dict[str, Any]] = [
        {"id": f"fabric:{fabric_id}", "label": fabric_name, "type": "fabric", "group": "fabric", "weight": 1}
    ]
    edges: List[Dict[str, Any]] = []

    for table in profile["tables"]:
        nodes.append({
            "id": f"collection:{table['name']}",
            "label": _humanize(table["name"]),
            "type": "collection",
            "group": "schema",
            "weight": max(int(table["row_count"]), 1),
            "properties": {
                "collection": table["name"],
                "kind": table["kind"],
                "documents_imported": table["row_count"],
                "rows_in_source": table["source_row_count"],
                "is_sample": table["is_sample"],
                "primary_key": table["primary_key"],
                "columns": [c["name"] for c in table["columns"]][:40],
            },
        })
        edges.append({
            "source": f"fabric:{fabric_id}",
            "target": f"collection:{table['name']}",
            "label": "contains", "type": "contains", "relation": "contains",
            "weight": max(int(table["row_count"]), 1),
        })

    for fk in profile.get("foreign_keys", []):
        edges.append({
            "source": f"collection:{fk['from_table']}",
            "target": f"collection:{fk['to_table']}",
            "label": fk["from_column"], "type": "references", "relation": "references",
            "weight": max(int(fk.get("matched_values") or 1), 1),
            "properties": {
                "from_column": fk["from_column"],
                "to_column": fk["to_column"],
                "cardinality": fk["cardinality"],
                "overlap": fk["overlap"],
                "confidence": fk["confidence"],
                "evidence": fk.get("evidence"),
                "evidence_refs": (
                    [{"basis": fk.get("evidence"), "overlap": fk.get("overlap")}]
                    if fk.get("evidence") is not None
                    else []
                ),
            },
        })

    # ---- sampled instances -------------------------------------------------
    instance_ids: Dict[Tuple[str, str], str] = {}
    per_table: Dict[str, int] = {}

    def add_instance(table: Dict[str, Any], row: Dict[str, Any], rowid: Any) -> Optional[str]:
        pk = table["primary_key"]
        key = "|".join(str(row.get(_col(table, c)["sql_name"])) for c in pk) if pk else f"row{rowid}"
        if (table["name"], key) in instance_ids:
            return instance_ids[(table["name"], key)]
        label_col = _col(table, table.get("label_column") or "") if table.get("label_column") else None
        label = str(row.get(label_col["sql_name"])) if label_col and row.get(label_col["sql_name"]) is not None else key
        node_id = _instance_id(table["name"], key)
        fields = {}
        for col in table["columns"][:12]:
            val = row.get(col["sql_name"])
            if val is not None and str(val) != "":
                fields[col["name"]] = val if not isinstance(val, (bytes, bytearray)) else str(val)
        nodes.append({
            "id": node_id,
            "label": label[:64],
            "type": "entity",
            "group": table["name"],
            "weight": 1,
            "properties": {
                "collection": table["name"],
                "sample": True,
                "row_id": key,
                "primary_key": table["primary_key"],
                "fields": fields,
            },
        })
        edges.append({
            "source": f"collection:{table['name']}", "target": node_id,
            "label": "includes", "type": "includes", "relation": "includes", "weight": 1,
        })
        instance_ids[(table["name"], key)] = node_id
        per_table[table["name"]] = per_table.get(table["name"], 0) + 1
        return node_id

    def fetch(table: Dict[str, Any], where: str = "", params: Tuple[Any, ...] = (), limit: int = per_table_limit):
        sql = f'SELECT rowid AS "__rowid", * FROM "{table["sql_name"]}" {where} LIMIT {int(limit)}'
        result = store.query(fabric_id, sql, params, max_rows=int(limit))
        return [dict(zip(result["columns"], r)) for r in result["rows"]]

    fks_from: Dict[str, List[Dict[str, Any]]] = {}
    for fk in profile.get("foreign_keys", []):
        fks_from.setdefault(fk["from_table"], []).append(fk)

    # Tables that reference others go first, so the rows they point at are the
    # parents that get sampled and the instance links are real.
    order = sorted(profile["tables"], key=lambda t: (-len(fks_from.get(t["name"], [])), t["name"]))
    sampled: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    for table in order:
        if not table["row_count"]:
            continue
        room = per_table_limit - per_table.get(table["name"], 0)
        if room <= 0:
            continue
        for row in fetch(table, limit=room):
            node_id = add_instance(table, row, row.get("__rowid"))
            if node_id:
                sampled.setdefault(table["name"], []).append((node_id, row))
        for fk in fks_from.get(table["name"], []):
            parent = tables.get(fk["to_table"])
            child_col = _col(table, fk["from_column"])
            parent_col = _col(parent, fk["to_column"]) if parent else None
            if not parent or not child_col or not parent_col:
                continue
            for node_id, row in sampled.get(table["name"], []):
                value = row.get(child_col["sql_name"])
                if value is None:
                    continue
                parent_node = None
                if parent["primary_key"] == [fk["to_column"]]:
                    parent_node = instance_ids.get((parent["name"], str(value)))
                if parent_node is None and per_table.get(parent["name"], 0) < per_table_limit * 2:
                    hits = fetch(parent, f'WHERE "{parent_col["sql_name"]}" = ?', (value,), limit=1)
                    if hits:
                        parent_node = add_instance(parent, hits[0], hits[0].get("__rowid"))
                        if parent_node:
                            sampled.setdefault(parent["name"], []).append((parent_node, hits[0]))
                if parent_node and parent_node != node_id:
                    edges.append({
                        "source": node_id, "target": parent_node,
                        "label": fk["from_column"], "type": "references", "relation": "references", "weight": 1,
                        "properties": {
                            "from_column": fk["from_column"],
                            "to_column": fk["to_column"],
                            "to_table": fk["to_table"],
                            "cardinality": fk.get("cardinality"),
                            "overlap": fk.get("overlap"),
                            "confidence": fk.get("confidence"),
                            "evidence": fk.get("evidence"),
                            "evidence_refs": (
                                [{"basis": fk.get("evidence"), "overlap": fk.get("overlap")}]
                                if fk.get("evidence") is not None
                                else []
                            ),
                            "basis": "profile_foreign_key",
                        },
                    })

    seen = set()
    unique_edges: List[Dict[str, Any]] = []
    for edge in edges:
        key = (edge["source"], edge["target"], edge["relation"], edge["label"])
        if key not in seen:
            seen.add(key)
            unique_edges.append(edge)

    total_rows = int(profile["summary"]["row_count"])
    sample_total = sum(per_table.values())
    return {
        "fabric_id": fabric_id,
        "fabric_name": fabric_name,
        "graph_type": "profiled_schema",
        "nodes": nodes,
        "edges": unique_edges,
        "node_count": len(nodes),
        "edge_count": len(unique_edges),
        "rendered_node_count": len(nodes),
        "rendered_edge_count": len(unique_edges),
        "document_total": total_rows,
        "document_sample_size": sample_total,
        "document_sample_capped": sample_total < total_rows,
        "graph_note": (
            f"Schema graph from the data profile: {len(profile['tables'])} tables and "
            f"{len(profile.get('foreign_keys', []))} relationships measured by value overlap. "
            f"Showing {sample_total:,} sample rows of {total_rows:,}, linked to the rows they reference."
        ),
    }
