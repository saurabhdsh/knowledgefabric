"""Migration JSON export / import helpers."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.services.codebase import ANALYSIS_VERSION, MIGRATION_SCHEMA


def build_migration_package(
    *,
    fabric: Dict[str, Any],
    inventory: Optional[Dict[str, Any]] = None,
    graph: Optional[Dict[str, Any]] = None,
    enrichment: Optional[Dict[str, Any]] = None,
    blueprint: Optional[Dict[str, Any]] = None,
    evidence_docs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    inventory = inventory or fabric.get("codebase_inventory") or {}
    graph = graph or fabric.get("code_graph") or {"nodes": [], "edges": []}
    enrichment = enrichment or {
        "module_summaries": fabric.get("module_summaries") or [],
        "domain_concepts": fabric.get("domain_concepts") or [],
        "discovery_summary": fabric.get("discovery_summary") or "",
    }
    blueprint = blueprint or fabric.get("migration_blueprint") or {}
    codebase_meta = fabric.get("codebase") or {}

    # Strip secrets / absolute paths
    safe_inventory = {
        k: v
        for k, v in inventory.items()
        if k not in ("all_relative_files",)  # keep sample only in export via files_sample
    }
    if "files_sample" not in safe_inventory and inventory.get("all_relative_files"):
        safe_inventory["files_sample"] = inventory["all_relative_files"][:200]
        safe_inventory["file_count"] = inventory.get("file_count") or len(inventory["all_relative_files"])

    evidence = []
    for doc in evidence_docs or []:
        evidence.append(
            {
                "path": doc.get("file_name") or doc.get("metadata", {}).get("path"),
                "kind": (doc.get("metadata") or {}).get("chunk_kind"),
                "content": (doc.get("content") or "")[:6000],
            }
        )
    # Also include module summaries as evidence for re-import
    if not evidence:
        for item in enrichment.get("module_summaries") or []:
            if isinstance(item, dict):
                evidence.append(
                    {
                        "path": f"module:{item.get('name')}",
                        "kind": "module_summary",
                        "content": str(item),
                    }
                )

    return {
        "schema": MIGRATION_SCHEMA,
        "manifest": {
            "fabric_id": fabric.get("id"),
            "name": fabric.get("name"),
            "source_type": "codebase",
            "analysis_version": ANALYSIS_VERSION,
            "exported_at": datetime.utcnow().isoformat(),
            "languages": (codebase_meta.get("languages") or inventory.get("languages") or {}),
            "frameworks": codebase_meta.get("frameworks") or inventory.get("frameworks") or [],
            "git_remote": codebase_meta.get("git_remote"),
            "git_ref": codebase_meta.get("git_ref"),
            "workspace_fingerprint": codebase_meta.get("workspace_fingerprint")
            or inventory.get("workspace_fingerprint"),
        },
        "inventory": safe_inventory,
        "graph": {
            "nodes": graph.get("nodes") or [],
            "edges": graph.get("edges") or [],
            "stats": graph.get("stats") or {},
        },
        "domain_map": {
            "concepts": enrichment.get("domain_concepts") or [],
            "module_summaries": enrichment.get("module_summaries") or [],
            "discovery_summary": enrichment.get("discovery_summary") or fabric.get("discovery_summary"),
        },
        "contracts": graph.get("contracts") or fabric.get("contracts") or [],
        "risks": blueprint.get("risks") or [],
        "blueprint": {
            "waves": blueprint.get("waves") or [],
            "bounded_contexts": blueprint.get("bounded_contexts") or [],
            "narrative": blueprint.get("narrative"),
            "migration_goal": blueprint.get("migration_goal"),
            "hotspots": blueprint.get("hotspots") or [],
        },
        "evidence": evidence[:300],
        "rag_index_meta": {
            "document_count": fabric.get("document_count") or 0,
            "total_chunks": fabric.get("total_chunks") or 0,
            "note": "Vectors are not embedded; re-index on import from evidence/summaries.",
        },
    }


def validate_migration_package(data: Dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ValueError("Migration package must be a JSON object.")
    schema = data.get("schema")
    if schema and schema != MIGRATION_SCHEMA:
        # allow forward-compatible if starts with weave.codebase.migration
        if not str(schema).startswith("weave.codebase.migration"):
            raise ValueError(f"Unsupported migration schema: {schema}")
    if "graph" not in data and "inventory" not in data:
        raise ValueError("Migration package missing graph/inventory.")
