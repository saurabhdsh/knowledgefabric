"""The three fabric builds, all on the same six stages (Release 2.0, Phase 1).

    run_document_pipeline   uploaded PDF / text files
    run_tabular_pipeline    database connections and CSV uploads
    run_composite_pipeline  several existing fabrics combined

Each returns the published fabric record or raises ``PipelineError`` after
marking the fabric ``failed`` and removing whatever was partly written.
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

from app.services.fabric_pipeline.chunker import chunk_document, chunk_to_vector_document
from app.services.fabric_pipeline.document_parser import (
    DocumentParseError,
    file_sha256,
    ocr_available,
    parse_document,
)
from app.services.fabric_pipeline.runner import PipelineError, PipelineRun, delete_manifest, load_profile
from app.services.fabric_pipeline.table_store import assign_sql_names, table_store
from app.services.fabric_pipeline.tabular_index import build_index_documents
from app.services.fabric_pipeline.tabular_profiler import apply_relationship_decisions, profile_tables
from app.services.fabric_pipeline.validators import failed, validate_documents, validate_tabular, index_count_check
from app.services.platform.reindex import embedding_stamp
from app.services.vector_service import vector_service
from app.utils.json_sanitize import sanitize_for_json

logger = logging.getLogger(__name__)

SUPPORTED_DOCUMENT_TYPES = (".pdf", ".txt", ".md", ".markdown")
TABULAR_CHUNK_TYPES = ("dataset", "schema", "entity", "text")


def _cleanup_failed(fabric_id: str) -> None:
    """Remove partly written vectors and tables; keep the manifest for diagnosis."""
    try:
        vector_service.delete_source_documents(fabric_id)
    except Exception:
        logger.debug("Vector cleanup failed for %s", fabric_id, exc_info=True)
    try:
        table_store.delete(fabric_id)
    except Exception:
        logger.debug("Table store cleanup failed for %s", fabric_id, exc_info=True)


def delete_fabric_artifacts(fabric_id: str) -> None:
    """Remove the table store and manifest of a deleted fabric."""
    try:
        table_store.delete(fabric_id)
    except Exception:
        logger.debug("Table store delete failed for %s", fabric_id, exc_info=True)
    delete_manifest(fabric_id)


def _raise_on_failed_checks(checks: List[Dict[str, Any]]) -> None:
    bad = failed(checks)
    if bad:
        raise PipelineError("; ".join(c["detail"] for c in bad))


def _schema_tables(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Profile as the table list stored on the fabric (read by ontology discovery and the graph)."""
    out: List[Dict[str, Any]] = []
    for table in profile["tables"]:
        fks = [
            {
                "column": fk["from_column"],
                "references_table": fk["to_table"],
                "references_column": fk["to_column"],
                "cardinality": fk["cardinality"],
                "confidence": fk["confidence"],
                "overlap": fk["overlap"],
                "evidence": fk.get("evidence"),
                "matched_values": fk.get("matched_values"),
                "orphan_values": fk.get("orphan_values"),
                "name_affinity": fk.get("name_affinity"),
                "parent_coverage": fk.get("parent_coverage"),
                "distinct_values": fk.get("distinct_values"),
                "value_confidence": fk.get("value_confidence"),
                "support": fk.get("support"),
                "status": fk.get("status") or "accepted",
                "confidence_basis": fk.get("confidence_basis"),
                "parent_is_sample": fk.get("parent_is_sample", False),
            }
            for fk in profile.get("foreign_keys", [])
            if fk["from_table"] == table["name"]
        ]
        composite = [
            {
                "columns": list(fk["from_columns"]),
                "references_table": fk["to_table"],
                "references_columns": list(fk["to_columns"]),
                "cardinality": fk["cardinality"],
                "confidence": fk["confidence"],
                "overlap": fk["overlap"],
                "evidence": fk.get("evidence"),
                "matched_values": fk.get("matched_values"),
                "orphan_values": fk.get("orphan_values"),
                "distinct_values": fk.get("distinct_values"),
                "status": fk.get("status") or "accepted",
                "confidence_basis": fk.get("confidence_basis"),
            }
            for fk in profile.get("composite_foreign_keys", [])
            if fk["from_table"] == table["name"]
        ]
        out.append({
            "name": table["name"],
            "kind": table["kind"],
            "row_count": table["row_count"],
            "source_row_count": table["source_row_count"],
            "is_sample": table["is_sample"],
            "primary_key": table["primary_key"],
            "label_column": table.get("label_column"),
            "foreign_keys": fks,
            "composite_foreign_keys": composite,
            "composite_key_candidates": table.get("composite_key_candidates") or [],
            "columns": [
                {
                    "name": c["name"],
                    "type": c["type"],
                    "role": c["role"],
                    "required": c["null_count"] == 0 and table["row_count"] > 0,
                    "null_rate": c["null_rate"],
                    "distinct_count": c["distinct_count"],
                }
                for c in table["columns"]
            ],
        })
    return out


def _tabular_record_fields(profile: Dict[str, Any], tables: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    schema = _schema_tables(profile)
    summary = profile["summary"]
    first_table = next((t for t in profile["tables"] if t["row_count"]), None)
    sample_rows: List[Dict[str, Any]] = []
    columns: List[str] = []
    if first_table:
        columns = [c["name"] for c in first_table["columns"]]
        sample_rows = [
            {k: v for k, v in row.items() if not str(k).startswith("__")}
            for row in (tables.get(first_table["name"]) or [])[:10]
        ]
    return {
        "tables": schema,
        "schema_tables": schema,
        "collections": [t["name"] for t in profile["tables"]],
        "per_collection": [
            {
                "name": t["name"],
                "documents_imported": t["row_count"],
                "rows_imported": t["row_count"],
                "rows_in_source": t["source_row_count"],
                "is_sample": t["is_sample"],
                "kind": t["kind"],
                "columns": [c["name"] for c in t["columns"]],
            }
            for t in profile["tables"]
        ],
        "relationships": [
            {
                k: fk[k]
                for k in (
                    "from_table", "from_column", "to_table", "to_column",
                    "cardinality", "overlap", "confidence", "evidence",
                    "matched_values", "orphan_values", "name_affinity",
                    "value_confidence", "support", "status", "confidence_basis",
                    "distinct_values", "parent_is_sample", "review_reasons",
                )
                if k in fk
            }
            for fk in profile.get("foreign_keys", [])
        ],
        # Two-column links, and links that wait for a reviewer. The second list
        # is shown for review and is not used to join, graph, or model anything.
        "composite_relationships": list(profile.get("composite_foreign_keys") or []),
        "relationship_candidates": list(profile.get("foreign_key_candidates") or []),
        "rows_imported": summary["row_count"],
        "rows_in_source": summary["source_row_count"],
        "is_sample": summary["is_sample"],
        "columns": columns,
        "sample_rows": sanitize_for_json(sample_rows),
    }


# ---------------------------------------------------------------- tabular


def run_tabular_pipeline(
    *,
    fabric_id: str,
    tables: Dict[str, List[Dict[str, Any]]],
    record: Dict[str, Any],
    source_row_counts: Optional[Dict[str, Optional[int]]] = None,
    inputs: Optional[Dict[str, Any]] = None,
    notes: Optional[List[str]] = None,
    progress_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a fabric from tables of rows (database import or CSV upload).

    ``source_row_counts``: rows each table holds in the source (``None`` when
    it could not be counted). ``notes``: things the import step wants on record,
    e.g. a row limit that was reached.
    """
    run = PipelineRun(fabric_id, "tabular", record, inputs=inputs, progress_id=progress_id)
    try:
        with run.stage("profile") as st:
            profile = profile_tables(tables, source_row_counts)
            apply_relationship_decisions(profile, record.get("relationship_decisions"))
            assign_sql_names(profile)
            if profile["summary"]["row_count"] == 0:
                raise PipelineError("The source returned no rows")
            for warning in list(notes or []) + profile["warnings"]:
                st.warn(warning)
            st.metrics(
                tables=profile["summary"]["table_count"],
                rows=profile["summary"]["row_count"],
                rows_in_source=profile["summary"]["source_row_count"],
                is_sample=profile["summary"]["is_sample"],
                columns=sum(len(t["columns"]) for t in profile["tables"]),
                primary_keys={t["name"]: t["primary_key"] for t in profile["tables"]},
                foreign_keys=len(profile["foreign_keys"]),
                two_column_foreign_keys=len(profile.get("composite_foreign_keys") or []),
                relationships_needing_review=profile["summary"].get("foreign_key_review_count", 0),
            )
            run.manifest["profile"] = profile

        with run.stage("parse") as st:
            stored = table_store.build(fabric_id, tables, profile)
            st.metrics(
                rows_loaded=sum(stored.values()),
                rows_per_table=stored,
                column_types={
                    t["name"]: {c["name"]: c["type"] for c in t["columns"]} for t in profile["tables"]
                },
                store="sqlite",
            )

        with run.stage("model") as st:
            documents, stats = build_index_documents(fabric_id, record.get("name") or fabric_id, profile, table_store)
            for warning in stats["warnings"]:
                st.warn(warning)
            st.metrics(
                table_kinds={t["name"]: t["kind"] for t in profile["tables"]},
                relationships=[
                    f"{fk['from_table']}.{fk['from_column']} -> {fk['to_table']}.{fk['to_column']} "
                    f"({fk['cardinality']}, overlap {fk['overlap']:.0%})"
                    for fk in profile["foreign_keys"]
                ],
                schema_cards=stats["schema_cards"],
                entity_summaries=stats["entity_summaries"],
                text_chunks=stats["text_chunks"],
                rows_embedded_as_chunks=0,
            )

        with run.stage("index") as st:
            ids = vector_service.add_documents(documents, fabric_id)
            run.manifest["embedding"] = embedding_stamp()
            st.metrics(chunks_indexed=len(ids), embedding_model=run.manifest["embedding"]["id"],
                       dimension=run.manifest["embedding"]["dimension"])

        with run.stage("validate") as st:
            checks = validate_tabular(fabric_id, tables, profile, table_store, documents)
            st.metrics(checks=checks)
            for check in checks:
                if check["status"] == "warn":
                    st.warn(check["detail"])
            _raise_on_failed_checks(checks)

        with run.stage("publish"):
            connection_info = dict(record.get("connection_info") or {})
            connection_info.update(_tabular_record_fields(profile, tables))
            run.publish({
                "connection_info": connection_info,
                "document_count": profile["summary"]["row_count"],
                "row_count": profile["summary"]["row_count"],
                "rows_in_source": profile["summary"]["source_row_count"],
                "is_sample": profile["summary"]["is_sample"],
                "table_count": profile["summary"]["table_count"],
                "total_chunks": len(ids),
                "has_table_store": True,
            })
        run.complete()
        return run.record
    except Exception as exc:
        _cleanup_failed(fabric_id)
        raise run.fail(exc) from exc


# --------------------------------------------------------------- document


def run_document_pipeline(
    *,
    fabric_id: str,
    files: List[Dict[str, Any]],
    record: Dict[str, Any],
    progress_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a fabric from uploaded documents.

    ``files``: resolved uploads, each ``{path, original_name, stored_name, size, sha256}``.
    Every named file must yield content; a file that cannot be read fails the build.
    """
    inputs = {
        "files": [
            {"original_name": f["original_name"], "stored_name": f["stored_name"]} for f in files
        ]
    }
    run = PipelineRun(fabric_id, "document", record, inputs=inputs, progress_id=progress_id)
    fabric_name = record.get("name") or fabric_id
    try:
        with run.stage("profile") as st:
            if not files:
                raise PipelineError("No files were given")
            can_ocr, ocr_reason = ocr_available()
            inventory: List[Dict[str, Any]] = []
            problems: List[str] = []
            for f in files:
                ext = os.path.splitext(f["original_name"])[1].lower() or os.path.splitext(f["stored_name"])[1].lower()
                size = os.path.getsize(f["path"]) if os.path.isfile(f["path"]) else 0
                if ext not in SUPPORTED_DOCUMENT_TYPES:
                    problems.append(f"'{f['original_name']}': unsupported type '{ext or 'none'}'")
                elif size == 0:
                    problems.append(f"'{f['original_name']}' is empty")
                inventory.append({
                    "original_name": f["original_name"],
                    "stored_name": f["stored_name"],
                    "type": ext.lstrip("."),
                    "bytes": size,
                    "sha256": f.get("sha256") or (file_sha256(f["path"]) if size else None),
                })
            if problems:
                raise PipelineError("; ".join(problems))
            if not can_ocr:
                st.warn(f"OCR is not available ({ocr_reason}); scanned pages cannot be read.")
            st.metrics(files=inventory, total_bytes=sum(i["bytes"] for i in inventory), ocr_available=can_ocr)
            run.manifest["inputs"]["files"] = inventory

        with run.stage("parse") as st:
            parsed_files: List[Dict[str, Any]] = []
            errors: List[str] = []
            for f in files:
                try:
                    parsed = parse_document(f["path"], f["original_name"])
                except DocumentParseError as exc:
                    errors.append(str(exc))
                    continue
                parsed["stored_name"] = f["stored_name"]
                parsed_files.append(parsed)
                for warning in parsed["warnings"]:
                    st.warn(warning)
            st.metrics(
                files={p["file_name"]: p["stats"] for p in parsed_files},
                pages=sum(p["stats"]["pages"] for p in parsed_files),
                pages_ocr=sum(p["stats"]["pages_ocr"] for p in parsed_files),
                pages_unreadable=sum(p["stats"]["pages_unreadable"] for p in parsed_files),
                tables=sum(p["stats"]["tables"] for p in parsed_files),
                failed_files=errors,
            )
            if errors:
                raise PipelineError("; ".join(errors))

        with run.stage("model") as st:
            chunks: List[Dict[str, Any]] = []
            outline: Dict[str, List[Dict[str, Any]]] = {}
            per_file: List[Dict[str, Any]] = []
            for parsed in parsed_files:
                file_chunks = chunk_document(parsed)
                for chunk in file_chunks:
                    chunk["stored_name"] = parsed["stored_name"]
                chunks.extend(file_chunks)
                outline[parsed["file_name"]] = [
                    {"level": b.get("level", 1), "title": b["text"], "page": b.get("page")}
                    for b in parsed["blocks"] if b["type"] == "heading"
                ][:300]
                per_file.append({
                    # ``filename`` is the stored file under the upload dir (ontology discovery opens it);
                    # ``original_name`` is what the user uploaded.
                    "filename": parsed["stored_name"] or parsed["file_name"],
                    "original_name": parsed["file_name"],
                    "stored_name": parsed["stored_name"],
                    "doc_id": fabric_id,
                    "chunks": len(file_chunks),
                    "pages": parsed["stats"]["pages"],
                    "pages_ocr": parsed["stats"]["pages_ocr"],
                    "pages_unreadable": parsed["stats"]["pages_unreadable"],
                    "tables": parsed["stats"]["tables"],
                    "sections": parsed["stats"]["headings"],
                })
            if not chunks:
                raise PipelineError("The documents produced no content to index")
            lengths = [len(c["content"]) for c in chunks]
            st.metrics(
                chunks=len(chunks),
                table_chunks=sum(1 for c in chunks if c["block_type"] == "table"),
                ocr_chunks=sum(1 for c in chunks if c["ocr"]),
                sections=sum(len(v) for v in outline.values()),
                avg_chunk_chars=round(sum(lengths) / len(lengths)),
                max_chunk_chars=max(lengths),
            )
            run.manifest["outline"] = outline

        with run.stage("index") as st:
            documents = [
                chunk_to_vector_document(c, fabric_name, c.get("stored_name", "")) for c in chunks
            ]
            ids = vector_service.add_documents(documents, fabric_id)
            run.manifest["embedding"] = embedding_stamp()
            st.metrics(chunks_indexed=len(ids), embedding_model=run.manifest["embedding"]["id"],
                       dimension=run.manifest["embedding"]["dimension"])

        with run.stage("validate") as st:
            checks = validate_documents(fabric_id, parsed_files, chunks, ids)
            st.metrics(checks=checks)
            for check in checks:
                if check["status"] == "warn":
                    st.warn(check["detail"])
            _raise_on_failed_checks(checks)

        with run.stage("publish"):
            run.publish({
                "document_count": len(parsed_files),
                "total_chunks": len(ids),
                "processed_files": per_file,
                "source_files": run.manifest["inputs"]["files"],
                "page_count": sum(p["stats"]["pages"] for p in parsed_files),
                "pages_ocr": sum(p["stats"]["pages_ocr"] for p in parsed_files),
                "pages_unreadable": sum(p["stats"]["pages_unreadable"] for p in parsed_files),
            })
        run.complete()
        return run.record
    except Exception as exc:
        _cleanup_failed(fabric_id)
        raise run.fail(exc) from exc


# -------------------------------------------------------------- composite


def _slug(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "_", str(value or "")).strip("_").lower()[:24] or "source"


def run_composite_pipeline(
    *,
    fabric_id: str,
    sources: List[Dict[str, Any]],
    record: Dict[str, Any],
    progress_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Combine existing fabrics into one.

    Tables of Release 2.0 tabular sources are merged into one table store and
    re-profiled together, so relationships *between* sources are discovered.
    Document chunks (and all chunks of pre-2.0 sources) are re-embedded under
    the composite with their origin recorded.
    """
    inputs = {"sources": [{"id": s.get("id"), "name": s.get("name"), "source_type": s.get("source_type")} for s in sources]}
    run = PipelineRun(fabric_id, "composite", record, inputs=inputs, progress_id=progress_id)
    fabric_name = record.get("name") or fabric_id
    try:
        with run.stage("profile") as st:
            inventory: List[Dict[str, Any]] = []
            for source in sources:
                sid = str(source.get("id"))
                if source.get("status") in ("failed", "building"):
                    raise PipelineError(f"Source '{source.get('name') or sid}' is {source.get('status')}; it cannot be combined")
                profile = load_profile(sid) if table_store.exists(sid) else None
                inventory.append({
                    "id": sid,
                    "name": source.get("name"),
                    "source_type": source.get("source_type"),
                    "pipeline_version": source.get("pipeline_version") or 1,
                    "chunks": vector_service.count_source_documents(sid),
                    "tables": [t["name"] for t in profile["tables"]] if profile else [],
                    "queryable_tables": bool(profile),
                })
                if (source.get("source_type") == "database") and not profile:
                    st.warn(
                        f"Source '{source.get('name') or sid}' was built before Release 2.0: its rows are "
                        f"copied as text chunks and cannot be queried by SQL. Re-create it to make it queryable."
                    )
            if not any(i["chunks"] or i["tables"] for i in inventory):
                raise PipelineError("None of the selected sources has any content")
            st.metrics(sources=inventory)

        with run.stage("parse") as st:
            tables: Dict[str, List[Dict[str, Any]]] = {}
            source_counts: Dict[str, Optional[int]] = {}
            table_origin: Dict[str, str] = {}
            copied: List[Dict[str, Any]] = []
            per_source: Dict[str, Dict[str, int]] = {}
            for source in sources:
                sid = str(source.get("id"))
                sname = source.get("name") or sid
                profile = load_profile(sid) if table_store.exists(sid) else None
                counts = {"rows": 0, "chunks_copied": 0}
                if profile:
                    for table in profile["tables"]:
                        name = table["name"]
                        if name in tables:
                            name = f"{_slug(sname)}__{table['name']}"
                            n = 2
                            while name in tables:
                                name, n = f"{_slug(sname)}_{n}__{table['name']}", n + 1
                        rows = table_store.original_rows(sid, profile, table=table["name"])
                        for row in rows:
                            row["__source_collection"] = name
                        tables[name] = rows
                        source_counts[name] = table.get("source_row_count")
                        table_origin[name] = sid
                        counts["rows"] += len(rows)
                for chunk in vector_service.list_source_chunks(sid, limit=0):
                    meta = dict(chunk.get("metadata") or {})
                    if profile and str(meta.get("chunk_type") or "") in TABULAR_CHUNK_TYPES:
                        continue  # rebuilt from the merged tables
                    content = str(chunk.get("content") or "").strip()
                    if not content:
                        continue
                    meta.pop("source_id", None)
                    meta.update({
                        "source_type": source.get("source_type", "unknown"),
                        "composite_parent_id": fabric_id,
                        "composite_origin_source_id": sid,
                        "composite_origin_source_name": sname,
                    })
                    copied.append({
                        "content": content,
                        "page_number": meta.get("page_number") or None,
                        "file_name": meta.get("file_name") or sname,
                        "source_name": sname,
                        "metadata": meta,
                    })
                    counts["chunks_copied"] += 1
                per_source[sid] = counts
            st.metrics(per_source=per_source, tables=len(tables), rows=sum(len(v) for v in tables.values()),
                       chunks_copied=len(copied))

        profile = None
        tabular_docs: List[Dict[str, Any]] = []
        with run.stage("model") as st:
            if tables:
                profile = profile_tables(tables, source_counts)
                apply_relationship_decisions(profile, record.get("relationship_decisions"))
                assign_sql_names(profile)
                for table in profile["tables"]:
                    table["origin_fabric_id"] = table_origin.get(table["name"])
                for warning in profile["warnings"]:
                    st.warn(warning)
                table_store.build(fabric_id, tables, profile)
                tabular_docs, stats = build_index_documents(fabric_id, fabric_name, profile, table_store)
                for warning in stats["warnings"]:
                    st.warn(warning)
                cross = [
                    fk for fk in profile["foreign_keys"]
                    if table_origin.get(fk["from_table"]) != table_origin.get(fk["to_table"])
                ]
                run.manifest["profile"] = profile
                st.metrics(
                    tables=profile["summary"]["table_count"],
                    rows=profile["summary"]["row_count"],
                    relationships=len(profile["foreign_keys"]),
                    cross_source_relationships=[
                        f"{fk['from_table']}.{fk['from_column']} -> {fk['to_table']}.{fk['to_column']} "
                        f"(overlap {fk['overlap']:.0%})"
                        for fk in cross
                    ],
                    entity_summaries=stats["entity_summaries"],
                    schema_cards=stats["schema_cards"],
                )
            else:
                st.metrics(tables=0, note="No queryable tables among the sources; document chunks only")

        with run.stage("index") as st:
            ids: List[str] = []
            if copied:
                ids.extend(vector_service.add_documents(copied, fabric_id))
            if tabular_docs:
                ids.extend(vector_service.add_documents(tabular_docs, fabric_id))
            if not ids:
                raise PipelineError("Nothing to index")
            run.manifest["embedding"] = embedding_stamp()
            st.metrics(chunks_indexed=len(ids), copied_chunks=len(copied), tabular_chunks=len(tabular_docs),
                       embedding_model=run.manifest["embedding"]["id"])

        entity_link_summary: Dict[str, Any] = {"link_count": 0, "chunk_count_linked": 0}
        with run.stage("validate") as st:
            if profile:
                checks = validate_tabular(fabric_id, tables, profile, table_store, tabular_docs)
                checks = [c for c in checks if c["check"] != "index_count"]
            else:
                checks = []
            checks.append(index_count_check(fabric_id, len(set(ids))))
            # Phase 3 — resolve document mentions against merged table rows
            if profile and copied:
                from app.services.fabric_pipeline.entity_resolution import link_document_chunks
                try:
                    entity_link_summary = link_document_chunks(fabric_id, profile, table_store)
                except Exception as exc:
                    st.warn(f"Entity resolution skipped: {exc}")
                    entity_link_summary = {"link_count": 0, "chunk_count_linked": 0, "error": str(exc)}
            unclear = int(entity_link_summary.get("ambiguous_name_count") or 0)
            st.metrics(
                checks=checks,
                entity_links=entity_link_summary.get("link_count", 0),
                entity_chunks_linked=entity_link_summary.get("chunk_count_linked", 0),
                entity_links_by_basis=entity_link_summary.get("by_basis") or {},
                ambiguous_names=unclear,
            )
            if unclear:
                st.warn(
                    f"{unclear} name mention(s) match more than one row and were linked to none. "
                    "They are listed under entity links for review."
                )
            for check in checks:
                if check["status"] == "warn":
                    st.warn(check["detail"])
            _raise_on_failed_checks(checks)

        with run.stage("publish"):
            from app.services.fabric_pipeline.composite_ontology import collect_source_ontology_refs

            ontology_refs = collect_source_ontology_refs(sources)
            source_fabrics = [
                {
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "source_type": s.get("source_type"),
                    "document_count": s.get("document_count", 0),
                    "total_chunks": s.get("total_chunks", 0),
                    "pipeline_version": s.get("pipeline_version") or 1,
                    "updated_at": s.get("updated_at"),
                    "ontology_project_id": s.get("ontology_project_id"),
                    "approved_ontology_version_id": s.get("approved_ontology_version_id"),
                }
                for s in sources
            ]
            updates: Dict[str, Any] = {
                "document_count": int(sum(int(s.get("document_count", 0) or 0) for s in sources)),
                "total_chunks": len(set(ids)),
                "source_fabric_ids": [s.get("id") for s in sources],
                "source_fabrics": source_fabrics,
                "composite_metadata": {
                    "source_count": len(sources),
                    "source_types": sorted({str(s.get("source_type", "unknown")) for s in sources}),
                    "materialized_chunks": len(set(ids)),
                    "copied_chunks": len(copied),
                    "tabular_chunks": len(tabular_docs),
                    "entity_links": entity_link_summary.get("link_count", 0),
                    "entity_chunks_linked": entity_link_summary.get("chunk_count_linked", 0),
                    "phase": 3,
                },
                "entity_links": {
                    "link_count": entity_link_summary.get("link_count", 0),
                    "chunk_count_linked": entity_link_summary.get("chunk_count_linked", 0),
                    "by_basis": entity_link_summary.get("by_basis") or {},
                    "ambiguous_name_count": entity_link_summary.get("ambiguous_name_count", 0),
                    "path": entity_link_summary.get("path"),
                },
                "shared_ontology": ontology_refs,
                "has_table_store": bool(profile),
                "last_refreshed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            if profile:
                updates["connection_info"] = {"type": "composite", **_tabular_record_fields(profile, tables)}
                updates["row_count"] = profile["summary"]["row_count"]
                updates["table_count"] = profile["summary"]["table_count"]
                updates["is_sample"] = profile["summary"]["is_sample"]
            run.publish(updates)
        run.complete()
        return run.record
    except Exception as exc:
        # On refresh, preserve the fabric record even if rebuild fails mid-way —
        # only wipe vectors/tables when this was a brand-new create (no prior status).
        if not (record.get("status") in ("active", "indexed") and record.get("source_fabric_ids")):
            _cleanup_failed(fabric_id)
        raise run.fail(exc) from exc


def refresh_composite_pipeline(
    *,
    fabric_id: str,
    progress_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Rebuild a composite from its live source fabrics (Phase 3 refresh).

    Keeps the same fabric id and ontology project; re-copies table stores and
    document chunks from the current source versions.
    """
    from app.services.platform.fabric_store import fabric_store

    fabric = fabric_store.get(fabric_id)
    if not fabric:
        raise PipelineError(f"Composite fabric not found: {fabric_id}", stage="refresh", fabric_id=fabric_id)
    if str(fabric.get("source_type") or "") != "composite":
        raise PipelineError(f"Fabric {fabric_id} is not a composite", stage="refresh", fabric_id=fabric_id)
    source_ids = list(fabric.get("source_fabric_ids") or [])
    if len(source_ids) < 2:
        raise PipelineError(
            "Composite has fewer than two source_fabric_ids; cannot refresh",
            stage="refresh",
            fabric_id=fabric_id,
        )

    sources: List[Dict[str, Any]] = []
    missing: List[str] = []
    for sid in source_ids:
        src = fabric_store.get(str(sid))
        if not src:
            missing.append(str(sid))
        else:
            sources.append(src)
    if missing:
        raise PipelineError(
            f"Source fabrics missing for refresh: {', '.join(missing)}",
            stage="refresh",
            fabric_id=fabric_id,
        )

    # Clear prior materialization; keep fabric metadata + ontology linkage.
    try:
        vector_service.delete_source_documents(fabric_id)
    except Exception:
        logger.debug("Vector clear failed during refresh of %s", fabric_id, exc_info=True)
    try:
        table_store.delete(fabric_id)
    except Exception:
        logger.debug("Table store clear failed during refresh of %s", fabric_id, exc_info=True)

    record = {
        "id": fabric_id,
        "name": fabric.get("name") or fabric_id,
        "source_type": "composite",
        "description": fabric.get("description") or "",
        "tags": list(fabric.get("tags") or []),
        "weave_domain": fabric.get("weave_domain"),
        "fabric_kind_label": fabric.get("fabric_kind_label"),
        "ontology_project_id": fabric.get("ontology_project_id"),
        "approved_ontology_version_id": fabric.get("approved_ontology_version_id"),
        "guardrails": fabric.get("guardrails"),
        "inherited_guardrails": fabric.get("inherited_guardrails"),
        "relationship_decisions": fabric.get("relationship_decisions"),
        "access": fabric.get("access"),
        "status": fabric.get("status") or "active",
        "source_fabric_ids": source_ids,
        "owner_id": fabric.get("owner_id"),
    }
    refreshed = run_composite_pipeline(
        fabric_id=fabric_id,
        sources=sources,
        record=record,
        progress_id=progress_id,
    )
    refreshed["refresh"] = {
        "mode": "full_rebuild",
        "source_count": len(sources),
        "refreshed_at": refreshed.get("last_refreshed_at"),
    }
    fabric_store.save(refreshed)
    return refreshed
