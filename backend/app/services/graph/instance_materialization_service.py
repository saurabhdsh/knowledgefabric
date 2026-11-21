"""Persist sampled instance nodes alongside the canonical class graph (Phase 2).

Instances come from the measured table-store profile (same builder used by the
live Data view). Node ids are hashed to fit ``graph_nodes.id`` (64 chars) while
preserving the logical ``instance:table:key`` id in properties.
"""
from __future__ import annotations

import hashlib
import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.services.fabric_pipeline.graph import build_profile_graph
from app.services.fabric_pipeline.runner import load_profile
from app.services.fabric_pipeline.table_store import table_store

logger = logging.getLogger(__name__)


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


class InstanceMaterializationService:
    def build_instance_payload(
        self,
        fabric: Dict[str, Any],
        *,
        class_nodes: List[Dict[str, Any]],
        per_table_limit: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Return (nodes, edges) ready for ``graph_store.insert_graph``.

        Class nodes from the ontology materializer are linked via ``instance_of``.
        Measured FK edges between sample rows keep confidence + evidence_refs.
        """
        if not settings.INSTANCE_GRAPH_ENABLED:
            return [], []
        fabric_id = str(fabric.get("id") or "")
        if not fabric_id or not table_store.exists(fabric_id):
            return [], []
        profile = load_profile(fabric_id)
        if not profile or not profile.get("tables"):
            return [], []

        limit = int(per_table_limit if per_table_limit is not None else settings.INSTANCE_GRAPH_PER_TABLE_LIMIT)
        live = build_profile_graph(fabric, profile, table_store, per_table_limit=limit)

        # Map collection / table name → ontology class node id
        class_by_table: Dict[str, str] = {}
        for n in class_nodes:
            props = n.get("properties") or {}
            candidates = [
                n.get("label"),
                n.get("normalized_name"),
                props.get("source_table"),
                n.get("source_table"),
            ]
            nid = n["id"]
            for c in candidates:
                if c:
                    class_by_table[_norm(str(c))] = nid
            # Plural/singular soft match against profile table names
            for table in profile["tables"]:
                tnorm = _norm(table["name"])
                for c in candidates:
                    if not c:
                        continue
                    cnorm = _norm(str(c))
                    if cnorm == tnorm or cnorm.rstrip("s") == tnorm.rstrip("s"):
                        class_by_table[tnorm] = nid

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        id_map: Dict[str, str] = {}  # ephemeral profile id → persisted id

        for n in live.get("nodes") or []:
            ntype = str(n.get("type") or "")
            nid = str(n.get("id") or "")
            if ntype == "entity" or nid.startswith("instance:"):
                props = dict(n.get("properties") or {})
                table = str(props.get("collection") or n.get("group") or "")
                row_key = str(props.get("row_id") or nid)
                persisted_id = _stable_id("gi", fabric_id, table, row_key)
                id_map[nid] = persisted_id
                props.update({
                    "node_kind": "instance",
                    "logical_id": nid,
                    "collection": table,
                    "sample": True,
                })
                nodes.append({
                    "id": persisted_id,
                    "ontology_class_id": None,
                    "label": str(n.get("label") or row_key)[:512],
                    "normalized_name": re.sub(r"\s+", "_", str(n.get("label") or row_key).lower())[:512],
                    "properties": props,
                    "source_table": table or None,
                    "source_column": None,
                })
                class_node = class_by_table.get(_norm(table))
                if class_node:
                    edges.append({
                        "id": _stable_id("ge", "instance_of", persisted_id, class_node),
                        "source_node_id": persisted_id,
                        "target_node_id": class_node,
                        "relationship_type": "instance_of",
                        "confidence": 1.0,
                        "evidence_refs": [{"basis": "profile_sample"}],
                        "properties": {"node_kind": "instance_link"},
                    })

        for e in live.get("edges") or []:
            if str(e.get("relation") or e.get("type") or "") != "references":
                continue
            src = id_map.get(str(e.get("source") or ""))
            tgt = id_map.get(str(e.get("target") or ""))
            if not src or not tgt or src == tgt:
                continue
            props = dict(e.get("properties") or {})
            evidence = props.get("evidence")
            evidence_refs = props.get("evidence_refs") or []
            if evidence and not evidence_refs:
                evidence_refs = [{"basis": evidence, "overlap": props.get("overlap")}]
            edges.append({
                "id": _stable_id("ge", "ref", src, tgt, props.get("from_column") or ""),
                "source_node_id": src,
                "target_node_id": tgt,
                "relationship_type": str(e.get("label") or "references"),
                "confidence": float(props.get("confidence") if props.get("confidence") is not None else 1.0),
                "evidence_refs": evidence_refs,
                "properties": {
                    **props,
                    "node_kind": "instance_fk",
                    "basis": props.get("basis") or "profile_foreign_key",
                },
            })

        logger.info(
            "Instance materialization for %s: %s nodes, %s edges (limit=%s)",
            fabric_id, len(nodes), len(edges), limit,
        )
        return nodes, edges


instance_materialization_service = InstanceMaterializationService()
