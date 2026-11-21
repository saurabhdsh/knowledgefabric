"""Cross-source entity resolution (Phase 3).

Find identifiers and person/place names inside document chunks (PDF policy,
care notes, …) and link them to rows in the composite table store — e.g.
"Lisa Chen" / ``MEM-LISA-COPD`` in a care-plan PDF → ``members`` row.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.config import settings
from app.services.fabric_pipeline.tabular_query import _candidate_tokens, find_entities
from app.services.fabric_pipeline.table_store import TableStore

logger = logging.getLogger(__name__)

# Document-like chunk types we scan for mentions (tabular summaries already know their row).
_DOC_CHUNK_TYPES = {"", "text", "section", "page", "paragraph", "heading", "ocr", "table"}
_TABULAR_SKIP = {"entity", "schema", "dataset", "row", "column"}


def _links_path(fabric_id: str) -> Path:
    base = Path(settings.DATA_DIR) / "fabric_entity_links"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{fabric_id}.json"


def extract_candidate_mentions(text: str) -> Tuple[List[str], List[str]]:
    """Identifier-like tokens and name phrases from a document passage."""
    return _candidate_tokens(text or "")


def resolve_mentions_against_profile(
    fabric_id: str,
    profile: Dict[str, Any],
    text: str,
    store: TableStore,
    *,
    max_entities: int = 4,
) -> List[Dict[str, Any]]:
    """Resolve mentions in ``text`` to table-store rows (exact id/label match)."""
    if not text or not profile:
        return []
    try:
        return find_entities(fabric_id, profile, text, store, max_entities=max_entities)
    except Exception as exc:
        logger.warning("Mention resolve failed for %s: %s", fabric_id, exc)
        return []


def _is_document_chunk(meta: Dict[str, Any]) -> bool:
    chunk_type = str(meta.get("chunk_type") or "").strip().lower()
    if chunk_type in _TABULAR_SKIP:
        return False
    # Prefer chunks that came from a non-tabular origin in a composite
    origin_type = str(meta.get("source_type") or "").lower()
    if origin_type in ("pdf", "document", "docx", "text", "image"):
        return True
    if meta.get("composite_origin_source_id") and chunk_type in _DOC_CHUNK_TYPES:
        return True
    if chunk_type in _DOC_CHUNK_TYPES and meta.get("file_name"):
        return True
    return chunk_type in {"section", "page", "ocr"}


def link_document_chunks(
    fabric_id: str,
    profile: Dict[str, Any],
    store: TableStore,
    *,
    vector_svc: Any = None,
    max_chunks: int = 2000,
    max_links_per_chunk: int = 3,
) -> Dict[str, Any]:
    """Scan document chunks, resolve mentions, persist links + chunk metadata.

    Returns ``{links, chunk_count_scanned, chunk_count_linked, path}``.
    """
    from app.services.vector_service import vector_service as default_vs

    vs = vector_svc or default_vs
    chunks = vs.list_source_chunks(fabric_id, limit=max_chunks)
    links: List[Dict[str, Any]] = []
    linked_chunk_ids: Set[str] = set()
    meta_updates: List[Tuple[str, Dict[str, Any]]] = []

    for chunk in chunks:
        meta = dict(chunk.get("metadata") or {})
        if not _is_document_chunk(meta):
            continue
        content = str(chunk.get("content") or "")
        if len(content) < 8:
            continue
        entities = resolve_mentions_against_profile(
            fabric_id, profile, content, store, max_entities=max_links_per_chunk
        )
        if not entities:
            continue
        chunk_id = str(chunk.get("id") or "")
        chunk_links = []
        for ent in entities:
            link = {
                "chunk_id": chunk_id,
                "table": ent["table"],
                "column": ent["matched_column"],
                "value": ent["matched_value"],
                "confidence": 1.0,
                "basis": "exact_mention",
                "origin_source_id": meta.get("composite_origin_source_id"),
                "origin_source_name": meta.get("composite_origin_source_name"),
                "file_name": meta.get("file_name"),
                "page_number": meta.get("page_number"),
                "row": {
                    k: ent["row"].get(k)
                    for k in list(ent["row"].keys())[:12]
                },
            }
            chunk_links.append(link)
            links.append(link)
        if chunk_id and chunk_links:
            linked_chunk_ids.add(chunk_id)
            new_meta = dict(meta)
            # Chroma metadata values must be scalars — store a compact JSON string.
            new_meta["linked_entities_json"] = json.dumps(
                [
                    {
                        "table": L["table"],
                        "column": L["column"],
                        "value": L["value"],
                        "confidence": L["confidence"],
                    }
                    for L in chunk_links
                ]
            )[:1800]
            new_meta["linked_entity_count"] = len(chunk_links)
            meta_updates.append((chunk_id, new_meta))

    if meta_updates and hasattr(vs, "update_chunk_metadatas"):
        try:
            vs.update_chunk_metadatas(fabric_id, meta_updates)
        except Exception as exc:
            logger.warning("Could not stamp linked_entities on chunks for %s: %s", fabric_id, exc)

    path = _links_path(fabric_id)
    payload = {
        "fabric_id": fabric_id,
        "link_count": len(links),
        "chunk_count_linked": len(linked_chunk_ids),
        "links": links,
    }
    try:
        path.write_text(json.dumps(payload, default=str), encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not write entity links file for %s: %s", fabric_id, exc)

    return {
        "links": links,
        "link_count": len(links),
        "chunk_count_scanned": len(chunks),
        "chunk_count_linked": len(linked_chunk_ids),
        "path": str(path),
    }


def load_entity_links(fabric_id: str) -> Dict[str, Any]:
    path = _links_path(fabric_id)
    if not path.exists():
        return {"fabric_id": fabric_id, "link_count": 0, "links": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"fabric_id": fabric_id, "link_count": 0, "links": []}


def linked_row_context_for_chunks(
    fabric_id: str,
    profile: Dict[str, Any],
    chunks: List[Dict[str, Any]],
    store: TableStore,
) -> str:
    """Build exact row context for entities linked from retrieved document chunks."""
    values: List[str] = []
    seen: Set[Tuple[str, str]] = set()
    for chunk in chunks:
        meta = chunk.get("metadata") or {}
        raw = meta.get("linked_entities_json")
        items: List[Dict[str, Any]] = []
        if raw:
            try:
                items = json.loads(raw) if isinstance(raw, str) else list(raw)
            except Exception:
                items = []
        for item in items:
            table = str(item.get("table") or "")
            value = str(item.get("value") or "")
            key = (table, value)
            if not table or not value or key in seen:
                continue
            seen.add(key)
            values.append(value)
    if not values:
        # Fall back to persisted link file for any value appearing in chunk text
        persisted = load_entity_links(fabric_id)
        for link in persisted.get("links") or []:
            value = str(link.get("value") or "")
            if value and any(value in str(c.get("content") or "") for c in chunks):
                values.append(value)
    if not values:
        return ""
    # Reuse find_entities with a synthetic query of known values
    synthetic = " ".join(dict.fromkeys(values))
    try:
        entities = find_entities(fabric_id, profile, synthetic, store, max_entities=4)
    except Exception:
        return ""
    if not entities:
        return ""
    from app.services.fabric_pipeline.tabular_query import entity_context_text
    return entity_context_text(entities)
