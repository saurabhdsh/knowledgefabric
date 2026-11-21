"""Re-embed existing fabrics with the active embedding model (Release 2.0, Phase 0).

Pre-2.0 fabrics were indexed with a per-process word hash, so their stored
vectors cannot be searched. This copies each fabric's chunks into the active
collection with real embeddings and records the model on the fabric.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from app.services.platform.fabric_store import fabric_store
from app.services.vector_service import vector_service

logger = logging.getLogger(__name__)


def embedding_stamp() -> Dict[str, Any]:
    """Embedding record stored on a fabric when its chunks are (re)indexed."""
    info = vector_service.embedding_info()
    return {
        "id": info["id"],
        "provider": info["provider"],
        "model": info["model"],
        "revision": info["revision"],
        "dimension": info["dimension"],
        "semantic": info["semantic"],
        "collection": info["collection"],
        "indexed_at": datetime.utcnow().isoformat() + "Z",
    }


def embedding_status(fabrics: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Active model plus, per fabric, whether its vectors need re-indexing."""
    fabrics = fabrics if fabrics is not None else fabric_store.list_all_dicts()
    rows: List[Dict[str, Any]] = []
    for fab in fabrics:
        fid = str(fab.get("id") or "")
        if not fid:
            continue
        info = vector_service.source_embedding_info(fid)
        chunks = vector_service.count_source_documents(fid)
        rows.append({
            "fabric_id": fid,
            "name": fab.get("name"),
            "chunks": chunks,
            "embedding_model": info.get("id"),
            "semantic": info.get("semantic"),
            "needs_reindex": bool(info.get("needs_reindex")) and chunks > 0,
        })
    return {
        "active_model": vector_service.embedding_info(),
        "fabrics": rows,
        "needs_reindex": sum(1 for r in rows if r["needs_reindex"]),
    }


def reindex_fabrics(
    fabric_ids: Optional[List[str]] = None,
    *,
    include_orphans: bool = False,
    purge_legacy: bool = False,
    progress: Optional[Callable[[float, str], None]] = None,
) -> Dict[str, Any]:
    """Re-embed fabrics that are not in the active collection.

    ``fabric_ids=None`` means every fabric in the store. ``include_orphans``
    also migrates legacy chunks whose fabric record no longer exists.
    ``purge_legacy`` deletes a fabric's old vectors after its copy is verified.
    """
    started = time.time()
    legacy_counts = vector_service.list_legacy_source_ids()
    known = {str(f.get("id")): f for f in fabric_store.list_all_dicts() if f.get("id")}

    if fabric_ids:
        targets = [fid for fid in fabric_ids if fid]
    else:
        targets = list(known.keys())
        if include_orphans:
            targets.extend(sid for sid in legacy_counts if sid not in known)

    total_chunks = sum(legacy_counts.get(fid, 0) for fid in targets) or 1
    done_chunks = 0
    results: List[Dict[str, Any]] = []

    for fid in targets:
        base_done = done_chunks

        def _on_progress(copied: int, total: int, _fid: str = fid, _base: int = base_done) -> None:
            if progress:
                progress(100.0 * (_base + copied) / total_chunks, f"Re-indexing {_fid}: {copied}/{total}")

        try:
            result = vector_service.reindex_source(fid, progress=_on_progress)
        except Exception as exc:
            logger.exception("Re-index failed for %s", fid)
            results.append({"source_id": fid, "status": "failed", "error": str(exc)})
            continue

        done_chunks += int(result.get("chunks") or 0) if result.get("status") != "current" else 0
        ok = result.get("status") in ("reindexed", "current")
        if ok and purge_legacy and result.get("status") == "reindexed":
            result["legacy_chunks_purged"] = vector_service.purge_legacy_source(fid)

        fabric = known.get(fid)
        if fabric is not None and ok and int(result.get("chunks") or 0) > 0:
            fabric["embedding"] = embedding_stamp()
            if fabric.get("model_status") in ("trained", "not_trained", "training", None, ""):
                fabric["model_status"] = "indexed"
            try:
                fabric_store.save(fabric)
            except Exception as exc:
                logger.warning("Could not stamp embedding on %s: %s", fid, exc)
        results.append(result)

    summary = {
        "active_model": vector_service.embedding_info(),
        "fabrics_considered": len(targets),
        "reindexed": sum(1 for r in results if r.get("status") == "reindexed"),
        "already_current": sum(1 for r in results if r.get("status") == "current"),
        "failed": [r for r in results if r.get("status") in ("failed", "incomplete")],
        "chunks_reindexed": sum(int(r.get("chunks") or 0) for r in results if r.get("status") == "reindexed"),
        "seconds": round(time.time() - started, 1),
        "results": results,
    }
    if progress:
        progress(100.0, "Re-index complete")
    return summary
