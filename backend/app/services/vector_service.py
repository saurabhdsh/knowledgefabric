"""Vector index over fabric chunks (Chroma).

Release 2.0 (Phase 0):

* Vectors come from a named, versioned embedding model
  (:mod:`app.services.embedding_service`), not from a per-process word hash.
* Each embedding model has its own collection, so vectors from different models
  are never compared. The pre-2.0 collection (``documents``) is kept read-only
  as *legacy*; :meth:`VectorService.reindex_source` re-embeds a fabric into the
  active collection.
* A fabric that still lives in the legacy collection cannot be vector-searched
  (its stored vectors were never stable), so it is ranked lexically (BM25) and
  the result says so.
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
import threading
import uuid
from collections import Counter
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import chromadb
from chromadb.config import Settings

from app.core.config import settings
from app.services.embedding_service import (
    LEGACY_COLLECTION,
    EmbeddingModel,
    collection_name_for,
    get_embedding_model,
)

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[a-z0-9]+")
_PAGE = 5000


def _tokens(text: str) -> List[str]:
    return _WORD_RE.findall(str(text or "").lower())


def lexical_scores(query: str, texts: List[str]) -> List[float]:
    """BM25 scores of ``texts`` for ``query``, scaled to 0..1 (best match = 1)."""
    q_terms = [t for t in dict.fromkeys(_tokens(query)) if len(t) > 1]
    if not q_terms or not texts:
        return [0.0] * len(texts)
    doc_tokens = [_tokens(t) for t in texts]
    doc_freq: Counter = Counter()
    for toks in doc_tokens:
        present = set(toks)
        for term in q_terms:
            if term in present:
                doc_freq[term] += 1
    n_docs = len(texts)
    avg_len = (sum(len(t) for t in doc_tokens) / n_docs) or 1.0
    k1, b = 1.5, 0.75
    scores: List[float] = []
    for toks in doc_tokens:
        tf = Counter(toks)
        length = len(toks) or 1
        score = 0.0
        for term in q_terms:
            freq = tf.get(term, 0)
            if not freq:
                continue
            idf = math.log(1.0 + (n_docs - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            score += idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * length / avg_len))
        scores.append(score)
    top = max(scores) if scores else 0.0
    return [s / top if top > 0 else 0.0 for s in scores]


class VectorService:
    def __init__(self) -> None:
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIRECTORY,
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )
        self.model_name = settings.MODEL_NAME
        self._lock = threading.RLock()
        self._collections: Dict[str, Any] = {}
        self._source_collection: Dict[str, str] = {}
        self.sources_collection = self.client.get_or_create_collection(
            name="sources", metadata={"hnsw:space": "cosine"}
        )

    # ------------------------------------------------------------------
    # Embedding model and collections
    # ------------------------------------------------------------------

    @property
    def embedder(self) -> EmbeddingModel:
        return get_embedding_model()

    def embedding_info(self) -> Dict[str, Any]:
        """The model new chunks are embedded with (recorded on each fabric)."""
        return self.embedder.info()

    def _collection(self, name: str, *, create: bool = False) -> Any:
        with self._lock:
            cached = self._collections.get(name)
            if cached is not None:
                return cached
            if create:
                collection = self.client.get_or_create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine", "embedding_model": self.embedder.id},
                )
            else:
                try:
                    collection = self.client.get_collection(name)
                except Exception:
                    return None
            self._collections[name] = collection
            return collection

    @property
    def active_collection_name(self) -> str:
        return collection_name_for(self.embedder.id)

    @property
    def documents_collection(self) -> Any:
        """Collection for the active embedding model (kept for existing callers)."""
        return self._collection(self.active_collection_name, create=True)

    @property
    def legacy_collection(self) -> Any:
        """Pre-2.0 collection with unstable 64-dim hash vectors, or ``None``."""
        if self.active_collection_name == LEGACY_COLLECTION:
            return None
        return self._collection(LEGACY_COLLECTION)

    @staticmethod
    def _has_source(collection: Any, source_id: str) -> bool:
        try:
            hit = collection.get(where={"source_id": source_id}, limit=1, include=[])
            return bool(hit.get("ids"))
        except Exception:
            return False

    def _collection_for_source(self, source_id: str) -> Any:
        """Collection that currently holds a fabric's chunks (active wins)."""
        active = self.documents_collection
        if not source_id:
            return active
        if settings.ISOLATE_FABRIC_INDEX and source_id:
            from app.services.enterprise.ops import isolated_collection_name

            isolated = self._collection(isolated_collection_name(source_id))
            if isolated is not None and self._has_source(isolated, source_id):
                self._source_collection[source_id] = isolated.name
                return isolated
        cached_name = self._source_collection.get(source_id)
        if cached_name:
            cached = self._collection(cached_name)
            if cached is not None:
                return cached
        if self._has_source(active, source_id):
            self._source_collection[source_id] = active.name
            return active
        candidates: List[Any] = []
        legacy = self.legacy_collection
        if legacy is not None:
            candidates.append(legacy)
        try:
            for col in self.client.list_collections():
                if col.name.startswith("kf_") and col.name != active.name:
                    candidates.append(self._collection(col.name))
        except Exception:
            pass
        for collection in candidates:
            if collection is not None and self._has_source(collection, source_id):
                self._source_collection[source_id] = collection.name
                return collection
        return active

    def _is_active(self, collection: Any) -> bool:
        return collection is not None and collection.name == self.active_collection_name

    def _vectors_current(self, collection: Any) -> bool:
        """True when ``collection`` holds vectors from the active embedding model.

        Per-fabric collections (``kf_f_*``) are current when they were created
        with this model. The shared legacy collection is not.
        """
        if collection is None:
            return False
        if collection.name == self.active_collection_name:
            return True
        try:
            meta = dict(getattr(collection, "metadata", None) or {})
        except Exception:
            meta = {}
        model = meta.get("embedding_model")
        return bool(model) and model == self.embedder.id

    def source_embedding_info(self, source_id: str) -> Dict[str, Any]:
        """Which model a fabric's stored vectors came from, and whether it needs re-indexing."""
        collection = self._collection_for_source(source_id)
        if self._vectors_current(collection):
            info = dict(self.embedding_info())
            info["collection"] = getattr(collection, "name", info.get("collection"))
            info["needs_reindex"] = False
            return info
        if collection is not None and collection.name == LEGACY_COLLECTION:
            return {
                "id": "legacy-process-hash-64",
                "provider": "legacy",
                "model": "python-hash-bag-of-words",
                "revision": "1.x",
                "dimension": 64,
                "semantic": False,
                "collection": LEGACY_COLLECTION,
                "needs_reindex": True,
            }
        return {
            "id": "unknown",
            "provider": "other",
            "collection": getattr(collection, "name", None),
            "semantic": None,
            "needs_reindex": True,
        }

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Embed texts with the active model. Raises if the model is unavailable."""
        return self.embedder.embed(texts)

    def _chroma_max_batch_size(self) -> int:
        """Chroma hard limit for a single add/upsert call (often ~41k)."""
        try:
            max_bs = self.client.get_max_batch_size()
            if isinstance(max_bs, int) and max_bs > 0:
                return max_bs
        except Exception:
            pass
        return 5000

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def _prepare_document_payload(
        self, documents: List[Dict[str, Any]], source_id: str, id_offset: int = 0
    ) -> tuple:
        texts: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        ids: List[str] = []
        for i, doc in enumerate(documents):
            content = str(doc["content"])
            texts.append(content)
            doc_metadata = doc.get("metadata", {}) or {}
            metadata = {
                **doc_metadata,
                # Enforce target source identity last so nested metadata cannot override it.
                "source_id": source_id,
                "source_name": doc.get("source_name", "Unknown"),
                "page_number": doc.get("page_number"),
                "file_name": doc.get("file_name"),
                "created_at": doc.get("created_at"),
            }
            # Chroma rejects None / nested values in metadata.
            cleaned: Dict[str, Any] = {}
            for key, value in metadata.items():
                if value is None:
                    cleaned[str(key)] = ""
                elif isinstance(value, (str, int, float, bool)):
                    cleaned[str(key)] = value
                else:
                    cleaned[str(key)] = str(value)
            metadatas.append(cleaned)
            explicit_id = doc.get("id")
            if explicit_id:
                ids.append(str(explicit_id))
            else:
                digest = hashlib.sha1(content.encode("utf-8", "ignore")).hexdigest()[:10]
                ids.append(f"{source_id}_{id_offset + i}_{digest}")
        return texts, metadatas, ids

    def add_documents(self, documents: List[Dict[str, Any]], source_id: str) -> List[str]:
        """Embed and store chunks for a fabric in the active collection.

        Chunk ids are derived from position and content, so re-running the same
        ingest overwrites rather than duplicates. Embedding failures propagate:
        a fabric must not be reported as indexed when it is not.
        """
        if not documents:
            return []

        if settings.ISOLATE_FABRIC_INDEX:
            from app.services.enterprise.ops import isolated_collection_name

            collection = self._collection(isolated_collection_name(source_id), create=True)
        else:
            current = self._collection_for_source(source_id)
            if not self._is_active(current) and self._has_source(current, source_id):
                # Keep a fabric in one collection: migrate it before appending.
                self.reindex_source(source_id)
            collection = self.documents_collection
        chunk_size = max(1, min(self._chroma_max_batch_size() - 1, 2000))
        all_ids: List[str] = []
        total = len(documents)
        for start in range(0, total, chunk_size):
            batch = documents[start : start + chunk_size]
            texts, metadatas, ids = self._prepare_document_payload(batch, source_id, id_offset=start)
            embeddings = self.create_embeddings(texts)
            collection.upsert(
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
                ids=ids,
            )
            all_ids.extend(ids)
            if total > chunk_size:
                logger.info("Indexed chunks %d-%d / %d for %s", start + 1, start + len(batch), total, source_id)
        self._source_collection[source_id] = collection.name
        return all_ids

    def add_documents_simple(
        self,
        documents: List[str],
        source_name: str,
        source_type: str,
        metadata: Dict[str, Any] = None,
    ) -> Optional[str]:
        """Add plain-text documents under a new generated source id."""
        if not documents:
            return None
        source_id = f"{source_type}_{uuid.uuid4().hex[:8]}"
        doc_list = []
        for i, doc in enumerate(documents):
            doc_metadata = dict(metadata or {})
            doc_metadata.update({
                "source_id": source_id,
                "source_name": source_name,
                "source_type": source_type,
                "file_type": source_type,
            })
            doc_list.append({
                "content": doc,
                "source_name": source_name,
                "page_number": i + 1,
                "file_name": source_name,
                "created_at": datetime.now().isoformat(),
                "metadata": doc_metadata,
            })
        self.add_documents(doc_list, source_id)
        return source_id

    def _delete_everywhere(self, source_id: str) -> None:
        """Drop a fabric's index without scanning collections that do not hold it.

        An isolated per-fabric collection is removed outright. Shared collections
        are filtered by source id, and a failure in one collection does not skip
        the others.
        """
        if not source_id:
            return
        with self._lock:
            if settings.ISOLATE_FABRIC_INDEX:
                from app.services.enterprise.ops import isolated_collection_name

                name = isolated_collection_name(source_id)
                self._collections.pop(name, None)
                try:
                    self.client.delete_collection(name)
                except Exception:
                    logger.debug("Isolated collection %s already gone", name, exc_info=True)
            for collection in (self.documents_collection, self.legacy_collection):
                if collection is None:
                    continue
                try:
                    found = collection.get(where={"source_id": source_id}, limit=1, include=[])
                    if found.get("ids"):
                        collection.delete(where={"source_id": source_id})
                except Exception:
                    logger.warning(
                        "Chunk delete failed in %s for %s",
                        getattr(collection, "name", "?"),
                        source_id,
                        exc_info=True,
                    )
            self._source_collection.pop(source_id, None)

    def delete_source_documents(self, source_id: str) -> bool:
        """Delete all chunks for a fabric (active and legacy collections)."""
        try:
            self._delete_everywhere(source_id)
            return True
        except Exception as e:
            logger.warning("Error deleting source documents for %s: %s", source_id, e)
            return False

    # Aliases used by other modules.
    delete_documents_by_source = delete_source_documents
    delete_source = delete_source_documents

    def update_chunk_metadatas(
        self,
        source_id: str,
        updates: List[Tuple[str, Dict[str, Any]]],
    ) -> int:
        """Update metadata for existing chunk ids (Phase 3 entity-link stamps)."""
        if not source_id or not updates:
            return 0
        collection = self._collection_for_source(source_id)
        ids = [str(i) for i, _ in updates if i]
        metadatas = [dict(m) for _, m in updates if _]
        if not ids:
            return 0
        # Ensure source_id is always present for where-filters.
        for meta in metadatas:
            meta.setdefault("source_id", source_id)
            cleaned = {}
            for key, value in meta.items():
                if value is None:
                    continue
                if isinstance(value, (str, int, float, bool)):
                    cleaned[str(key)] = value
                else:
                    cleaned[str(key)] = str(value)
            meta.clear()
            meta.update(cleaned)
        try:
            # Chroma update batches — keep modest.
            step = 200
            for start in range(0, len(ids), step):
                collection.update(
                    ids=ids[start:start + step],
                    metadatas=metadatas[start:start + step],
                )
            return len(ids)
        except Exception as exc:
            logger.warning("update_chunk_metadatas failed for %s: %s", source_id, exc)
            return 0

    # ------------------------------------------------------------------
    # Re-indexing (legacy -> active)
    # ------------------------------------------------------------------

    def list_legacy_source_ids(self) -> Dict[str, int]:
        """Chunk counts per source id still stored in the legacy collection."""
        legacy = self.legacy_collection
        counts: Dict[str, int] = {}
        if legacy is None:
            return counts
        offset = 0
        while True:
            batch = legacy.get(include=["metadatas"], limit=_PAGE, offset=offset)
            metas = batch.get("metadatas") or []
            if not metas:
                break
            for meta in metas:
                sid = str((meta or {}).get("source_id") or "")
                if sid:
                    counts[sid] = counts.get(sid, 0) + 1
            if len(metas) < _PAGE:
                break
            offset += _PAGE
        return counts

    def reindex_source(
        self,
        source_id: str,
        progress: Optional[Callable[[int, int], None]] = None,
        page_size: int = 512,
    ) -> Dict[str, Any]:
        """Re-embed one fabric's chunks with the active model.

        Non-destructive: chunks are copied into the active collection and the
        old collection is left untouched. Returns counts so the caller can
        verify nothing was dropped.
        """
        source = self._collection_for_source(source_id)
        active = self.documents_collection
        if self._is_active(source):
            return {
                "source_id": source_id,
                "status": "current",
                "chunks": self._count_in(active, source_id),
                "collection": active.name,
            }
        total = self._count_in(source, source_id)
        copied = 0
        offset = 0
        while True:
            batch = source.get(
                where={"source_id": source_id},
                include=["documents", "metadatas"],
                limit=page_size,
                offset=offset,
            )
            ids = batch.get("ids") or []
            if not ids:
                break
            docs = [str(d or " ") for d in (batch.get("documents") or [])]
            metas = [dict(m) if m else {"source_id": source_id} for m in (batch.get("metadatas") or [])]
            embeddings = self.create_embeddings(docs)
            active.upsert(ids=ids, embeddings=embeddings, documents=docs, metadatas=metas)
            copied += len(ids)
            offset += len(ids)
            if progress:
                progress(copied, total)
            if len(ids) < page_size:
                break
        in_active = self._count_in(active, source_id)
        if in_active >= total:
            self._source_collection[source_id] = active.name
        return {
            "source_id": source_id,
            "status": "reindexed" if in_active >= total else "incomplete",
            "chunks": total,
            "chunks_in_active": in_active,
            "from_collection": source.name,
            "collection": active.name,
            "embedding": self.embedding_info(),
        }

    def purge_legacy_source(self, source_id: str) -> int:
        """Delete a fabric's chunks from the legacy collection (after a verified re-index)."""
        legacy = self.legacy_collection
        if legacy is None:
            return 0
        before = self._count_in(legacy, source_id)
        if before:
            legacy.delete(where={"source_id": source_id})
        return before

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    @staticmethod
    def _count_in(collection: Any, source_id: str) -> int:
        total = 0
        offset = 0
        while True:
            batch = collection.get(where={"source_id": source_id}, include=[], limit=_PAGE, offset=offset)
            ids = batch.get("ids") or []
            total += len(ids)
            if len(ids) < _PAGE:
                break
            offset += _PAGE
        return total

    def count_source_documents(self, source_id: str) -> int:
        """How many chunks are stored for a fabric."""
        try:
            return self._count_in(self._collection_for_source(source_id), source_id)
        except Exception as e:
            logger.warning("Error counting source documents for %s: %s", source_id, e)
            return 0

    def get_source_statistics(self, source_id: str) -> Dict[str, Any]:
        count = self.count_source_documents(source_id)
        return {
            "source_id": source_id,
            "document_count": count,
            "status": "active" if count > 0 else "empty",
            "embedding": self.source_embedding_info(source_id),
        }

    def get_source_documents(
        self,
        source_id: str,
        limit: Optional[int] = None,
        *,
        source_collection: Optional[str] = None,
        chunk_type: Optional[str] = None,
    ):
        """Get stored chunks for a fabric.

        Pass ``limit`` for large fabrics so callers do not pull every chunk into
        memory. ``source_collection`` / ``chunk_type`` filter on chunk metadata.
        """
        try:
            clauses: List[Dict[str, Any]] = [{"source_id": source_id}]
            if source_collection:
                clauses.append({"source_collection": str(source_collection)})
            if chunk_type:
                clauses.append({"chunk_type": str(chunk_type)})
            where: Dict[str, Any] = clauses[0] if len(clauses) == 1 else {"$and": clauses}
            kwargs: Dict[str, Any] = {"where": where}
            if limit is not None and int(limit) > 0:
                kwargs["limit"] = int(limit)
            return self._collection_for_source(source_id).get(**kwargs)
        except Exception as e:
            logger.warning("Error getting source documents for %s: %s", source_id, e)
            if chunk_type:
                return self.get_source_documents(
                    source_id, limit=limit, source_collection=source_collection, chunk_type=None
                )
            return {"documents": [], "metadatas": [], "ids": []}

    def list_source_chunks(self, source_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return stored chunks for a fabric, unranked.

        Default caps at 5000. Pass ``limit=0`` (or negative) for every chunk.
        Chunks carry ``similarity_score`` 0.0 until a ranker scores them.
        """
        if limit is None:
            effective_limit: Optional[int] = 5000
        elif int(limit) <= 0:
            effective_limit = None
        else:
            effective_limit = int(limit)

        def _to_chunks(documents, metadatas, ids, rank_start: int) -> List[Dict[str, Any]]:
            out: List[Dict[str, Any]] = []
            for i, content in enumerate(documents):
                meta = metadatas[i] if i < len(metadatas) and isinstance(metadatas[i], dict) else {}
                out.append({
                    "content": content,
                    "metadata": meta,
                    "similarity_score": 0.0,
                    "rank": rank_start + i,
                    "id": ids[i] if i < len(ids) else f"{source_id}_{rank_start + i - 1}",
                    "chunk_type": str(meta.get("chunk_type", "")).strip().lower(),
                })
            return out

        collection = self._collection_for_source(source_id)
        chunks: List[Dict[str, Any]] = []
        offset = 0
        try:
            while True:
                page = _PAGE
                if effective_limit is not None:
                    page = min(_PAGE, effective_limit - len(chunks))
                    if page <= 0:
                        break
                batch = collection.get(where={"source_id": source_id}, limit=page, offset=offset)
                documents = batch.get("documents") or []
                if not documents:
                    break
                chunks.extend(
                    _to_chunks(documents, batch.get("metadatas") or [], batch.get("ids") or [], len(chunks) + 1)
                )
                if len(documents) < page:
                    break
                offset += len(documents)
        except Exception as e:
            logger.warning("Error listing source chunks for %s: %s", source_id, e)
        return chunks

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _rank_lexically(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        scores = lexical_scores(query, [str(c.get("content") or "") for c in chunks])
        for chunk, score in zip(chunks, scores):
            chunk["similarity_score"] = float(score)
            chunk["ranker"] = "lexical-bm25"
        chunks.sort(key=lambda c: float(c.get("similarity_score") or 0.0), reverse=True)
        for i, chunk in enumerate(chunks):
            chunk["rank"] = i + 1
        return chunks

    def find_chunks_containing(self, source_id: str, token: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Chunks of a fabric whose text contains ``token`` exactly (case-sensitive).

        Embeddings are poor at telling identifiers apart (CLM-00017 vs CLM-00071);
        this gives exact-token recall for codes and ids mentioned in a question.
        """
        if not source_id or not token or len(token) < 3:
            return []
        try:
            batch = self._collection_for_source(source_id).get(
                where={"source_id": source_id},
                where_document={"$contains": token},
                limit=int(limit),
            )
        except Exception as exc:
            logger.warning("Exact-token lookup failed for %s (%s)", source_id, exc)
            return []
        documents = batch.get("documents") or []
        metadatas = batch.get("metadatas") or []
        ids = batch.get("ids") or []
        return [
            {
                "content": content,
                "metadata": metadatas[i] if i < len(metadatas) and isinstance(metadatas[i], dict) else {},
                "similarity_score": 1.0,
                "rank": i + 1,
                "id": ids[i] if i < len(ids) else None,
                "ranker": "exact-token",
            }
            for i, content in enumerate(documents)
        ]

    def search_similar_chunks(self, query: str, source_id: str = None, top_k: int = 3) -> List[Dict[str, Any]]:
        """Rank a fabric's chunks for a query.

        ``top_k <= 0`` returns every chunk, ranked. Each chunk reports its
        ``ranker``: ``vector:<model id>`` when the fabric is in the active
        collection, ``lexical-bm25`` when it is not (legacy fabric awaiting
        re-index, or the embedding model failed at query time).
        """
        want_all = top_k is None or int(top_k) <= 0
        collection = self._collection_for_source(source_id) if source_id else self.documents_collection
        vector_ok = self._vectors_current(collection)
        ranker = f"vector:{self.embedder.id}"

        query_embedding: Optional[List[float]] = None
        if vector_ok:
            try:
                query_embedding = self.create_embeddings([query])[0]
            except Exception as exc:
                logger.warning("Query embedding failed (%s); ranking lexically", exc)
                vector_ok = False

        try:
            if source_id and want_all:
                all_chunks = self.list_source_chunks(source_id, limit=0)
                if not all_chunks:
                    return []
                if not vector_ok:
                    return self._rank_lexically(query, all_chunks)
                try:
                    results = collection.query(
                        query_embeddings=[query_embedding],
                        n_results=len(all_chunks),
                        where={"source_id": source_id},
                    )
                    scored: Dict[str, float] = {}
                    if results.get("ids") and results["ids"][0]:
                        for doc_id, distance in zip(results["ids"][0], results["distances"][0]):
                            scored[str(doc_id)] = 1.0 - float(distance)
                    for chunk in all_chunks:
                        chunk["similarity_score"] = scored.get(str(chunk.get("id")), 0.0)
                        chunk["ranker"] = ranker
                    all_chunks.sort(key=lambda c: float(c.get("similarity_score") or 0.0), reverse=True)
                    for i, chunk in enumerate(all_chunks):
                        chunk["rank"] = i + 1
                    return all_chunks
                except Exception as rank_exc:
                    logger.warning("Vector ranking failed for %s (%s); ranking lexically", source_id, rank_exc)
                    return self._rank_lexically(query, all_chunks)

            requested = max(1, int(top_k) if top_k is not None else 3)

            if not vector_ok:
                if not source_id:
                    return []
                ranked = self._rank_lexically(query, self.list_source_chunks(source_id, limit=0))
                return ranked[:requested]

            available = self.count_source_documents(source_id) if source_id else 0
            if available > 0:
                requested = min(requested, available)
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=requested,
                where={"source_id": source_id} if source_id else None,
            )
            processed: List[Dict[str, Any]] = []
            if results["documents"] and results["documents"][0]:
                ids = results.get("ids", [[]])[0]
                for i, (doc, metadata, distance) in enumerate(zip(
                    results["documents"][0], results["metadatas"][0], results["distances"][0]
                )):
                    processed.append({
                        "content": doc,
                        "metadata": metadata,
                        "similarity_score": 1 - distance,
                        "rank": i + 1,
                        "id": ids[i] if i < len(ids) else None,
                        "ranker": ranker,
                    })
            return processed
        except Exception as e:
            logger.warning("Error in search_similar_chunks for %s: %s", source_id, e)
            if source_id:
                try:
                    ranked = self._rank_lexically(query, self.list_source_chunks(source_id, limit=0))
                    return ranked if want_all else ranked[: max(1, int(top_k))]
                except Exception:
                    return []
            return []

    def search_documents(
        self,
        query: str,
        limit: int = 5,
        threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search across all fabrics in the active collection."""
        query_embedding = self.create_embeddings([query])[0]
        where_clause = dict(filters) if filters else None
        results = self.documents_collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where=where_clause,
        )
        processed_results = []
        if results["documents"] and results["documents"][0]:
            for i, (doc, metadata, distance) in enumerate(zip(
                results["documents"][0], results["metadatas"][0], results["distances"][0]
            )):
                similarity_score = 1 - distance
                if similarity_score >= threshold:
                    processed_results.append({
                        "id": results["ids"][0][i],
                        "content": doc,
                        "source": metadata.get("source_name", "Unknown"),
                        "similarity_score": similarity_score,
                        "metadata": metadata,
                        "page_number": metadata.get("page_number"),
                    })
        return processed_results

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def _source_counts(self) -> Dict[str, Dict[str, Any]]:
        """Chunk counts and first-seen metadata per source in the active collection."""
        sources: Dict[str, Dict[str, Any]] = {}
        collection = self.documents_collection
        offset = 0
        while True:
            batch = collection.get(include=["metadatas"], limit=_PAGE, offset=offset)
            metas = batch.get("metadatas") or []
            if not metas:
                break
            for meta in metas:
                sid = (meta or {}).get("source_id")
                if not sid:
                    continue
                entry = sources.setdefault(sid, {"count": 0, "meta": meta})
                entry["count"] += 1
            if len(metas) < _PAGE:
                break
            offset += _PAGE
        return sources

    def get_all_statistics(self) -> Dict[str, Any]:
        collection = self.documents_collection
        total_documents = collection.count()
        legacy = self.legacy_collection
        return {
            "total_documents": total_documents,
            "total_sources": len(self._source_counts()),
            "total_embeddings": total_documents,
            "model_name": self.embedder.model_name,
            "embedding": self.embedding_info(),
            "legacy_documents_awaiting_reindex": legacy.count() if legacy is not None else 0,
        }

    def get_stats(self):
        try:
            total_documents = self.documents_collection.count()
            return {
                "total_sources": len(self._source_counts()),
                "total_documents": total_documents,
                "total_embeddings": total_documents,
                "model_status": "active",
                "last_training": None,
                "embedding": self.embedding_info(),
            }
        except Exception as e:
            logger.warning("Error getting stats: %s", e)
            return {
                "total_sources": 0,
                "total_documents": 0,
                "total_embeddings": 0,
                "model_status": "inactive",
                "last_training": None,
            }

    def update_model(self, new_model_name: str) -> bool:
        """Kept for API compatibility. The embedding model is set by configuration
        (``EMBEDDING_PROVIDER`` / ``MODEL_NAME``) because changing it requires a re-index."""
        logger.warning(
            "update_model(%s) ignored: change EMBEDDING_PROVIDER/MODEL_NAME and re-index instead.",
            new_model_name,
        )
        return False

    def get_all_sources(self):
        """Sources present in the active collection, with chunk counts."""
        try:
            source_list = []
            for source_id, entry in self._source_counts().items():
                meta = entry["meta"] or {}
                count = entry["count"]
                source_list.append({
                    "id": source_id,
                    "name": meta.get("source_name", "Unknown"),
                    "source_type": meta.get("file_type", "unknown"),
                    "description": meta.get("description", ""),
                    "tags": meta.get("tags", []),
                    "created_at": meta.get("created_at"),
                    "updated_at": meta.get("created_at"),
                    "document_count": count,
                    "status": "active",
                    "model_status": "indexed" if count > 0 else "not_indexed",
                    "last_training": None,
                    "chunks_count": count,
                    "embedding_count": count,
                })
            return source_list
        except Exception as e:
            logger.warning("Error getting all sources: %s", e)
            return []

    def get_source(self, source_id: str):
        try:
            for source in self.get_all_sources():
                if source["id"] == source_id:
                    return source
            return None
        except Exception as e:
            logger.warning("Error getting source %s: %s", source_id, e)
            return None

    def export_source(self, source_id: str):
        try:
            source = self.get_source(source_id)
            if not source:
                return None
            return {"source": source, "documents": self.get_source_documents(source_id)}
        except Exception as e:
            logger.warning("Error exporting source: %s", e)
            return None


# Global instance
vector_service = VectorService()
