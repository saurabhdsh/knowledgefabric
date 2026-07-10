"""Build RAG chunks from codebase analysis."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def build_vector_documents(
    *,
    root: Path,
    inventory: Dict[str, Any],
    graph: Dict[str, Any],
    enrichment: Dict[str, Any],
    blueprint: Dict[str, Any],
) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    now = datetime.utcnow().isoformat()

    summary = enrichment.get("discovery_summary") or ""
    if summary:
        docs.append(
            {
                "content": f"Codebase discovery summary:\n{summary}",
                "page_number": 1,
                "file_name": "discovery_summary.md",
                "source_name": "codebase-analysis",
                "created_at": now,
                "metadata": {"source_type": "codebase", "chunk_kind": "discovery_summary"},
            }
        )

    if blueprint.get("narrative"):
        docs.append(
            {
                "content": f"Migration blueprint:\n{blueprint['narrative']}\n\nWaves:\n{blueprint.get('waves')}",
                "page_number": 1,
                "file_name": "migration_blueprint.md",
                "source_name": "codebase-analysis",
                "created_at": now,
                "metadata": {"source_type": "codebase", "chunk_kind": "blueprint"},
            }
        )

    for item in enrichment.get("module_summaries") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or "module"
        content = (
            f"Module: {name}\n"
            f"Purpose: {item.get('purpose')}\n"
            f"Layer: {item.get('layer')}\n"
            f"Risks: {item.get('risks')}\n"
        )
        files = (graph.get("module_files") or {}).get(name) or []
        content += "Files:\n" + "\n".join(files[:30])
        # Attach a small code sample from first file
        if files:
            sample_path = root / files[0]
            if sample_path.is_file():
                try:
                    snippet = sample_path.read_text(encoding="utf-8", errors="ignore")[:2500]
                    content += f"\n\nSample from {files[0]}:\n{snippet}"
                except OSError:
                    pass
        docs.append(
            {
                "content": content,
                "page_number": 1,
                "file_name": f"module_{name}.md",
                "source_name": name,
                "created_at": now,
                "metadata": {
                    "source_type": "codebase",
                    "chunk_kind": "module_summary",
                    "module": name,
                },
            }
        )

    # Evidence chunks from important entrypoints / API files
    for rel in (inventory.get("entrypoints") or [])[:20]:
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")[:4000]
        except OSError:
            continue
        docs.append(
            {
                "content": f"Entrypoint file {rel}:\n{text}",
                "page_number": 1,
                "file_name": rel,
                "source_name": rel,
                "created_at": now,
                "metadata": {"source_type": "codebase", "chunk_kind": "entrypoint", "path": rel},
            }
        )

    for contract in (graph.get("contracts") or [])[:40]:
        docs.append(
            {
                "content": f"API contract {contract.get('name')} in {contract.get('path')}",
                "page_number": 1,
                "file_name": str(contract.get("path") or "api"),
                "source_name": "api-contracts",
                "created_at": now,
                "metadata": {"source_type": "codebase", "chunk_kind": "api_contract", **contract},
            }
        )

    return docs
