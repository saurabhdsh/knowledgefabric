"""Bridge Knowledge Fabric sources (PDF, etc.) into ontology discovery artifacts."""
from __future__ import annotations

import html
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.models.ontology import SourceArtifact
from app.services.platform.fabric_store import fabric_store
from app.services.vector_service import vector_service


def _source_type_from_name(file_name: str, fallback: str = "xml") -> str:
    ext = os.path.splitext(file_name)[1].lower()
    if ext == ".pdf":
        return "pdf"
    if ext == ".docx":
        return "docx"
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        return "image"
    if ext == ".xml":
        return "xml"
    return fallback


def _materialize_fabric_documents_to_xml(fabric_id: str) -> Optional[str]:
    docs_payload = vector_service.get_source_documents(fabric_id)
    documents = docs_payload.get("documents") if isinstance(docs_payload, dict) else []
    if not isinstance(documents, list) or not documents:
        return None

    upload_dir = settings.ONTOLOGY_UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    file_name = f"{fabric_id}_fabric_source.xml"
    file_path = os.path.join(upload_dir, file_name)

    selected_docs = [str(doc) for doc in documents[:300] if isinstance(doc, str) and doc.strip()]
    if not selected_docs:
        return None

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("<fabricSource>\n")
        for idx, chunk in enumerate(selected_docs, start=1):
            f.write(f'  <chunk id="{idx}">{html.escape(chunk)}</chunk>\n')
        f.write("</fabricSource>\n")
    return file_path


def resolve_artifacts_for_fabric(fabric_id: str, project_id: str) -> List[SourceArtifact]:
    """Find or materialize ontology-readable artifacts for a knowledge fabric."""
    fabric = fabric_store.get(fabric_id)
    if not fabric:
        return []

    linked: List[SourceArtifact] = []
    processed_files = fabric.get("processed_files") if isinstance(fabric.get("processed_files"), list) else []
    candidate_roots = [
        settings.ONTOLOGY_UPLOAD_DIR,
        settings.UPLOAD_DIR,
    ]

    for item in processed_files:
        if not isinstance(item, dict):
            continue
        file_name = str(item.get("filename") or "").strip()
        if not file_name:
            continue
        for root in candidate_roots:
            if not root:
                continue
            file_path = os.path.join(root, file_name)
            if not os.path.isfile(file_path):
                continue
            linked.append(
                SourceArtifact(
                    id=f"art_{uuid.uuid4().hex[:12]}",
                    file_name=file_name,
                    file_path=os.path.abspath(file_path),
                    source_type=_source_type_from_name(file_name, fallback="xml"),
                    project_id=project_id,
                    ingestion_time=datetime.utcnow(),
                    metadata={"fabric_id": fabric_id, "linked_from": "processed_files"},
                )
            )
            break

    if not linked:
        materialized_path = _materialize_fabric_documents_to_xml(fabric_id)
        if materialized_path and os.path.isfile(materialized_path):
            file_name = os.path.basename(materialized_path)
            linked.append(
                SourceArtifact(
                    id=f"art_{uuid.uuid4().hex[:12]}",
                    file_name=file_name,
                    file_path=os.path.abspath(materialized_path),
                    source_type="xml",
                    project_id=project_id,
                    ingestion_time=datetime.utcnow(),
                    metadata={"fabric_id": fabric_id, "linked_from": "vector_documents"},
                )
            )

    return linked


def artifact_paths_for_discovery(artifacts: List[SourceArtifact]) -> List[str]:
    """Return absolute file paths for the discovery orchestrator."""
    return [a.file_path for a in artifacts if a.file_path and os.path.isfile(a.file_path)]
