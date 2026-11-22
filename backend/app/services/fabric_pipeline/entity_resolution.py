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
from app.services.fabric_pipeline.tabular_profiler import table_by_name
from app.services.fabric_pipeline.tabular_query import (
    _candidate_tokens,
    entity_context_text,
    find_entities,
    rows_by_reference,
)
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
    ambiguous_out: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Resolve mentions in a document passage to table-store rows.

    An identifier links at full confidence. A name links only when it is
    written as a name and points at one row: a name shared by several rows is
    linked to none of them unless the passage also carries a second fact (a
    birth date, an identifier) that belongs to exactly one of those rows.
    """
    if not text or not profile:
        return []
    try:
        return find_entities(
            fabric_id, profile, text, store,
            max_entities=max_entities,
            strict_names=True,
            ambiguous_names="skip",
            ambiguous_out=ambiguous_out,
        )
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
    ambiguous: List[Dict[str, Any]] = []
    meta_updates: List[Tuple[str, Dict[str, Any]]] = []

    for chunk in chunks:
        meta = dict(chunk.get("metadata") or {})
        if not _is_document_chunk(meta):
            continue
        content = str(chunk.get("content") or "")
        if len(content) < 8:
            continue
        chunk_id = str(chunk.get("id") or "")
        unclear: List[Dict[str, Any]] = []
        entities = resolve_mentions_against_profile(
            fabric_id, profile, content, store,
            max_entities=max_links_per_chunk, ambiguous_out=unclear,
        )
        for item in unclear:
            ambiguous.append({
                "chunk_id": chunk_id,
                "name": item["name"],
                "row_count": item["row_count"],
                "tables": item["tables"],
                "file_name": meta.get("file_name"),
                "page_number": meta.get("page_number"),
            })
        if not entities:
            continue
        chunk_links = []
        for ent in entities:
            table = table_by_name(profile, ent["table"]) or {}
            pk = list(table.get("primary_key") or [])
            key_column = pk[0] if len(pk) == 1 else None
            link = {
                "chunk_id": chunk_id,
                "table": ent["table"],
                "column": ent["matched_column"],
                "value": ent["matched_value"],
                "key_column": key_column,
                "key_value": ent["row"].get(key_column) if key_column else None,
                "confidence": ent.get("confidence", 1.0),
                "basis": ent.get("basis", "identifier"),
                "second_fact": ent.get("second_fact"),
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
                        "key_column": L["key_column"],
                        "key_value": L["key_value"],
                        "confidence": L["confidence"],
                        "basis": L["basis"],
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
        "by_basis": _count_by_basis(links),
        # Names that match several rows with nothing in the passage to pick
        # one. They are listed for review and linked to no row.
        "ambiguous_names": ambiguous[:500],
        "ambiguous_name_count": len(ambiguous),
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
        "by_basis": payload["by_basis"],
        "ambiguous_names": ambiguous[:500],
        "ambiguous_name_count": len(ambiguous),
        "path": str(path),
    }


def _count_by_basis(links: List[Dict[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for link in links:
        basis = str(link.get("basis") or "identifier")
        out[basis] = out.get(basis, 0) + 1
    return out


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
    refs: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, str]] = set()

    def _add(item: Dict[str, Any]) -> None:
        table = str(item.get("table") or "")
        # Follow the row's own key when the link kept one; a name is followed
        # only if it still selects a single row.
        column = item.get("key_column") or item.get("column")
        value = item.get("key_value") if item.get("key_column") else item.get("value")
        key = (table, str(column), str(value))
        if not table or not column or value in (None, "") or key in seen:
            return
        seen.add(key)
        refs.append({
            "table": table, "column": column, "value": value,
            "basis": item.get("basis"), "confidence": item.get("confidence"),
        })

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
            _add(item)
    if not refs:
        # Fall back to the persisted links of exactly these chunks.
        chunk_ids = {str(c.get("id") or "") for c in chunks}
        for link in load_entity_links(fabric_id).get("links") or []:
            value = str(link.get("value") or "")
            if str(link.get("chunk_id") or "") in chunk_ids or (
                value and any(value in str(c.get("content") or "") for c in chunks)
            ):
                _add(link)
    if not refs:
        return ""
    try:
        entities = rows_by_reference(fabric_id, profile, refs, store, max_entities=4)
    except Exception:
        return ""
    if not entities:
        return ""
    return entity_context_text(entities)
