"""Import a migration JSON package into a new codebase fabric."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from app.core.user_context import get_current_user_id
from app.services.codebase import ANALYSIS_VERSION, MIGRATION_SCHEMA
from app.services.codebase.migration_export import validate_migration_package
from app.services.platform.fabric_store import fabric_store
from app.services.vector_service import vector_service


def import_migration_package(
    package: Dict[str, Any],
    *,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    validate_migration_package(package)
    manifest = package.get("manifest") or {}
    inventory = package.get("inventory") or {}
    graph = package.get("graph") or {"nodes": [], "edges": []}
    domain = package.get("domain_map") or {}
    blueprint = package.get("blueprint") or {}
    evidence = package.get("evidence") or []

    fabric_id = f"fabric_codebase_import_{uuid.uuid4().hex[:10]}"
    now = datetime.utcnow().isoformat()
    fabric_name = name or manifest.get("name") or f"Imported Codebase {fabric_id[-6:]}"

    docs = []
    if domain.get("discovery_summary"):
        docs.append(
            {
                "content": f"Imported discovery summary:\n{domain['discovery_summary']}",
                "page_number": 1,
                "file_name": "discovery_summary.md",
                "source_name": "import",
                "created_at": now,
                "metadata": {"source_type": "codebase", "chunk_kind": "discovery_summary"},
            }
        )
    if blueprint.get("narrative"):
        docs.append(
            {
                "content": f"Imported migration blueprint:\n{blueprint.get('narrative')}\nWaves: {blueprint.get('waves')}",
                "page_number": 1,
                "file_name": "migration_blueprint.md",
                "source_name": "import",
                "created_at": now,
                "metadata": {"source_type": "codebase", "chunk_kind": "blueprint"},
            }
        )
    for item in domain.get("module_summaries") or []:
        if isinstance(item, dict):
            docs.append(
                {
                    "content": str(item),
                    "page_number": 1,
                    "file_name": f"module_{item.get('name')}.md",
                    "source_name": item.get("name") or "module",
                    "created_at": now,
                    "metadata": {"source_type": "codebase", "chunk_kind": "module_summary"},
                }
            )
    for ev in evidence[:200]:
        if not isinstance(ev, dict):
            continue
        content = ev.get("content") or ""
        if not content:
            continue
        docs.append(
            {
                "content": content,
                "page_number": 1,
                "file_name": str(ev.get("path") or "evidence"),
                "source_name": "evidence",
                "created_at": now,
                "metadata": {
                    "source_type": "codebase",
                    "chunk_kind": ev.get("kind") or "evidence",
                },
            }
        )

    chunk_ids = vector_service.add_documents(docs, fabric_id) if docs else []

    fabric = {
        "id": fabric_id,
        "name": fabric_name,
        "source_type": "codebase",
        "description": "Imported from Weave migration JSON",
        "status": "active",
        "model_status": "not_trained",
        "document_count": len(docs),
        "total_chunks": len(chunk_ids) or len(docs),
        "tags": ["codebase", "imported", "migration"],
        "created_at": now,
        "updated_at": now,
        "owner_id": get_current_user_id(),
        "codebase": {
            "input_mode": "import",
            "languages": manifest.get("languages") or inventory.get("languages") or {},
            "frameworks": manifest.get("frameworks") or inventory.get("frameworks") or [],
            "file_count": inventory.get("file_count") or 0,
            "module_count": inventory.get("module_count") or len(inventory.get("modules") or []),
            "git_remote": manifest.get("git_remote"),
            "git_ref": manifest.get("git_ref"),
            "analyzed_at": now,
            "analysis_version": ANALYSIS_VERSION,
            "workspace_fingerprint": manifest.get("workspace_fingerprint"),
            "imported_from_schema": package.get("schema") or MIGRATION_SCHEMA,
        },
        "codebase_inventory": inventory,
        "code_graph": {
            "nodes": graph.get("nodes") or [],
            "edges": graph.get("edges") or [],
            "stats": graph.get("stats") or {},
            "contracts": package.get("contracts") or [],
        },
        "contracts": package.get("contracts") or [],
        "module_summaries": domain.get("module_summaries") or [],
        "domain_concepts": domain.get("concepts") or [],
        "discovery_summary": domain.get("discovery_summary") or "",
        "migration_blueprint": {
            "waves": blueprint.get("waves") or [],
            "bounded_contexts": blueprint.get("bounded_contexts") or [],
            "risks": package.get("risks") or blueprint.get("risks") or [],
            "narrative": blueprint.get("narrative"),
            "migration_goal": blueprint.get("migration_goal"),
            "hotspots": blueprint.get("hotspots") or [],
        },
    }
    fabric_store.save(fabric)
    return fabric
