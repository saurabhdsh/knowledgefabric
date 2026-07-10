"""End-to-end codebase analysis pipeline."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from app.services.codebase import ANALYSIS_VERSION
from app.services.codebase.blueprint import apply_graph_additions, build_blueprint
from app.services.codebase.chunker import build_vector_documents
from app.services.codebase.enrichment import enrich_modules, merge_enrichment_into_graph
from app.services.codebase.ingest import workspace_dir
from app.services.codebase.inventory import build_inventory
from app.services.codebase.structural_graph import build_structural_graph
from app.services.platform.fabric_store import fabric_store
from app.services.vector_service import vector_service

logger = logging.getLogger(__name__)

ProgressCb = Callable[[float, str, Optional[Dict[str, Any]]], None]


def _noop_progress(pct: float, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
    return None


def run_codebase_pipeline(
    fabric_id: str,
    config: Optional[Dict[str, Any]] = None,
    progress: Optional[ProgressCb] = None,
) -> Dict[str, Any]:
    config = config or {}
    report = progress or _noop_progress

    fabric = fabric_store.get(fabric_id)
    if not fabric:
        raise ValueError(f"Fabric not found: {fabric_id}")

    root = Path(config.get("workspace_path") or workspace_dir(fabric_id))
    if not root.is_dir():
        raise ValueError(f"Workspace not found at {root}")

    exclude = config.get("exclude_globs") or []
    migration_goal = config.get("migration_goal")

    report(8.0, "Building inventory", {"stage": "inventory"})
    inventory = build_inventory(root, extra_exclude=exclude)

    report(30.0, "Building structural graph", {"stage": "structural"})
    graph = build_structural_graph(root, inventory)

    report(55.0, "Enriching with LLM", {"stage": "enrichment"})
    enrichment = enrich_modules(
        inventory=inventory,
        graph=graph,
        migration_goal=migration_goal,
    )
    graph = merge_enrichment_into_graph(graph, enrichment)

    report(72.0, "Creating migration blueprint", {"stage": "blueprint"})
    blueprint = build_blueprint(
        inventory=inventory,
        graph=graph,
        enrichment=enrichment,
        migration_goal=migration_goal,
    )
    graph = apply_graph_additions(graph, blueprint.get("graph_additions") or {})

    report(85.0, "Indexing for retrieval", {"stage": "chunks"})
    docs = build_vector_documents(
        root=root,
        inventory=inventory,
        graph=graph,
        enrichment=enrichment,
        blueprint=blueprint,
    )
    try:
        # Clear prior vectors for re-analyze when possible
        if hasattr(vector_service, "delete_documents_by_source"):
            vector_service.delete_documents_by_source(fabric_id)  # type: ignore[attr-defined]
    except Exception:
        logger.debug("Could not clear prior vectors for %s", fabric_id, exc_info=True)

    chunk_ids = []
    if docs:
        chunk_ids = vector_service.add_documents(docs, fabric_id)

    report(94.0, "Persisting fabric", {"stage": "persist"})
    now = datetime.utcnow().isoformat()
    codebase_meta = {
        "input_mode": config.get("input_mode") or fabric.get("codebase", {}).get("input_mode"),
        "languages": inventory.get("languages") or {},
        "frameworks": inventory.get("frameworks") or [],
        "file_count": inventory.get("file_count") or 0,
        "module_count": inventory.get("module_count") or 0,
        "git_remote": config.get("git_url") or fabric.get("codebase", {}).get("git_remote"),
        "git_ref": config.get("git_ref") or fabric.get("codebase", {}).get("git_ref"),
        "analyzed_at": now,
        "analysis_version": ANALYSIS_VERSION,
        "workspace_fingerprint": inventory.get("workspace_fingerprint"),
        "workspace_path": str(root),
    }

    # Drop bulky all_relative_files from stored inventory (keep sample)
    stored_inventory = {
        k: v for k, v in inventory.items() if k != "all_relative_files"
    }

    fabric.update(
        {
            "status": "active",
            "source_type": "codebase",
            "document_count": len(docs),
            "total_chunks": len(chunk_ids) or len(docs),
            "updated_at": now,
            "tags": sorted(set((fabric.get("tags") or []) + ["codebase", "workspace", "migration"])),
            "codebase": codebase_meta,
            "codebase_inventory": stored_inventory,
            "code_graph": {
                "nodes": graph.get("nodes") or [],
                "edges": graph.get("edges") or [],
                "stats": graph.get("stats") or {},
                "contracts": graph.get("contracts") or [],
                "data_entities": graph.get("data_entities") or [],
                "module_files": graph.get("module_files") or {},
            },
            "contracts": graph.get("contracts") or [],
            "module_summaries": enrichment.get("module_summaries") or [],
            "domain_concepts": enrichment.get("domain_concepts") or [],
            "discovery_summary": enrichment.get("discovery_summary") or "",
            "migration_blueprint": {
                k: v for k, v in blueprint.items() if k != "graph_additions"
            },
            "analysis_job_id": config.get("job_id") or fabric.get("analysis_job_id"),
        }
    )
    fabric_store.save(fabric)
    report(100.0, "Codebase fabric ready", {"stage": "done", "fabric_id": fabric_id})
    return {
        "fabric_id": fabric_id,
        "inventory": stored_inventory,
        "graph_stats": graph.get("stats") or {},
        "chunk_count": len(chunk_ids) or len(docs),
    }
