"""Ontology Discovery API endpoints."""
import os
import threading
import uuid
import json
import html
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiofiles
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse

from app.models.knowledge import APIResponse
from app.models.ontology import (
    OntologyClass,
    OntologyRelationship,
    OntologyAttribute,
    OntologyElementStatus,
    SourceArtifact,
    GovernanceMode,
    ChangeStatus,
)
from app.schemas.ontology import (
    DiscoverOntologyRequest,
    OntologyClassUpdate,
    OntologyRelationshipUpdate,
    OntologyAttributeUpdate,
    ReviewApproveRequest,
    ReviewRejectRequest,
    MergeRequest,
    CreateProjectRequest,
    AddArtifactsRequest,
    OntologyChatRequest,
    EnrichmentDiscoverRequest,
    CandidateReviewRequest,
    GovernanceModeUpdateRequest,
    EnrichmentDiscoverFromProjectRequest,
    CreateProjectFromFabricRequest,
    AgentQueryRequest,
    AgentDataContractUpsertRequest,
    AgentDataContractDeleteRequest,
    AgentPolicyEvaluateRequest,
)
from app.services.ontology import (
    ArtifactLoader,
    OntologyPersistenceService,
    DiscoveryOrchestrator,
    OntologyExportService,
    OntologyEnrichmentService,
)
from app.services.ontology.llm_ontology_service import LLMOntologyService
from app.services.vector_service import vector_service
from app.core.config import settings
from app.services.platform.fabric_store import fabric_store
from app.services.ontology.ontology_access import (
    allowed_project_ids,
    register_project_owner,
    user_owns_project,
)

router = APIRouter()
persistence = OntologyPersistenceService()
artifact_loader = ArtifactLoader()
export_service = OntologyExportService()
llm_ontology = LLMOntologyService()
enrichment_service = OntologyEnrichmentService(persistence=persistence)
FABRICS_STORAGE_FILE = os.path.join(settings.DATA_DIR, "fabrics.json")
AGENT_UTILS_STATE_FILE = os.path.join(settings.DATA_DIR, "agent_utilities_state.json")


def _source_type_from_name(file_name: str, fallback: str = "xml") -> str:
    ext = os.path.splitext(file_name.lower())[1]
    if ext == ".pdf":
        return "pdf"
    if ext == ".docx":
        return "docx"
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        return "image"
    if ext == ".xml":
        return "xml"
    return fallback


def _extract_fabric_reference_from_project(project: Any) -> Dict[str, Optional[str]]:
    description = getattr(project, "description", None) or ""
    if not isinstance(description, str):
        return {"fabric_id": None, "fabric_name": None}
    # Expected shape: "(id: <fabric_id>, source_type: ...)"
    marker = "id:"
    idx = description.lower().find(marker)
    fabric_id: Optional[str] = None
    if idx >= 0:
        tail = description[idx + len(marker):]
        candidate = tail.split(",", 1)[0].strip().strip(").")
        fabric_id = candidate or None

    fabric_name: Optional[str] = None
    quote_marker = "knowledge fabric '"
    qidx = description.lower().find(quote_marker)
    if qidx >= 0:
        start = qidx + len(quote_marker)
        end = description.find("'", start)
        if end > start:
            fabric_name = description[start:end].strip() or None

    return {"fabric_id": fabric_id, "fabric_name": fabric_name}


def _load_fabric_by_id(fabric_id: str) -> Optional[Dict[str, Any]]:
    if not fabric_id or not os.path.exists(FABRICS_STORAGE_FILE):
        return None
    try:
        with open(FABRICS_STORAGE_FILE, "r", encoding="utf-8") as f:
            fabrics = json.load(f)
        if not isinstance(fabrics, list):
            return None
        return next((item for item in fabrics if isinstance(item, dict) and item.get("id") == fabric_id), None)
    except Exception:
        return None


def _load_fabric_by_name(fabric_name: str) -> Optional[Dict[str, Any]]:
    if not fabric_name or not os.path.exists(FABRICS_STORAGE_FILE):
        return None
    try:
        with open(FABRICS_STORAGE_FILE, "r", encoding="utf-8") as f:
            fabrics = json.load(f)
        if not isinstance(fabrics, list):
            return None
        target = fabric_name.strip().lower()
        return next(
            (item for item in fabrics if isinstance(item, dict) and str(item.get("name", "")).strip().lower() == target),
            None,
        )
    except Exception:
        return None


def _materialize_fabric_documents_to_xml(fabric_id: str) -> Optional[str]:
    docs_payload = vector_service.get_source_documents(fabric_id)
    documents = docs_payload.get("documents") if isinstance(docs_payload, dict) else []
    if not isinstance(documents, list) or not documents:
        return None

    upload_dir = getattr(settings, "ONTOLOGY_UPLOAD_DIR", None) or os.path.join(settings.ONTOLOGY_DATA_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    file_name = f"{fabric_id}_fabric_source.xml"
    file_path = os.path.join(upload_dir, file_name)

    # Keep generated source bounded for fast discovery runs.
    selected_docs = [str(doc) for doc in documents[:300] if isinstance(doc, str) and doc.strip()]
    if not selected_docs:
        return None

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("<fabricSource>\n")
        for idx, chunk in enumerate(selected_docs, start=1):
            f.write(f'  <chunk id="{idx}">{html.escape(chunk)}</chunk>\n')
        f.write("</fabricSource>\n")
    return file_path


def _ensure_fabric_artifacts_for_project(project: Any) -> List[str]:
    project_id = getattr(project, "id", "")
    existing = getattr(project, "source_artifacts", None) or []
    existing_paths = [a.file_name for a in existing if getattr(a, "file_name", None)]
    if existing_paths:
        return existing_paths

    ref = _extract_fabric_reference_from_project(project)
    fabric_id = ref.get("fabric_id")
    fabric_name = ref.get("fabric_name")
    fabric = _load_fabric_by_id(fabric_id) if fabric_id else None
    if not fabric and fabric_name:
        fabric = _load_fabric_by_name(fabric_name)
        if fabric:
            fabric_id = str(fabric.get("id") or "")
    if not fabric_id:
        return []

    linked_artifacts: List[SourceArtifact] = []
    processed_files = fabric.get("processed_files") if isinstance(fabric, dict) and isinstance(fabric.get("processed_files"), list) else []
    candidate_roots = [
        getattr(settings, "ONTOLOGY_UPLOAD_DIR", None) or os.path.join(settings.ONTOLOGY_DATA_DIR, "uploads"),
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
            linked_artifacts.append(
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

    if not linked_artifacts:
        materialized_path = _materialize_fabric_documents_to_xml(fabric_id)
        if materialized_path and os.path.isfile(materialized_path):
            file_name = os.path.basename(materialized_path)
            linked_artifacts.append(
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

    if linked_artifacts:
        persistence.add_artifacts_to_project(project_id, linked_artifacts)
        return [a.file_name for a in linked_artifacts]
    return []


def _load_agent_utils_state() -> Dict[str, Any]:
    if not os.path.exists(AGENT_UTILS_STATE_FILE):
        return {"contracts": [], "query_logs": []}
    try:
        with open(AGENT_UTILS_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"contracts": [], "query_logs": []}
        data.setdefault("contracts", [])
        data.setdefault("query_logs", [])
        return data
    except Exception:
        return {"contracts": [], "query_logs": []}


def _save_agent_utils_state(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(AGENT_UTILS_STATE_FILE), exist_ok=True)
    with open(AGENT_UTILS_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _compute_trust_score(version: Any, selected: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    classes = getattr(version, "classes", []) or []
    relationships = getattr(version, "relationships", []) or []
    attributes = getattr(version, "attributes", []) or []
    all_elements = [*classes, *relationships, *attributes]
    if not all_elements:
        return {
            "overall_score": 0,
            "confidence_score": 0,
            "approval_score": 0,
            "coverage_score": 0,
            "freshness_score": 0,
            "explanation": "No ontology elements found for trust scoring.",
        }

    confidence_values = [float(getattr(el, "confidence_score", 0) or 0) for el in all_elements]
    confidence_score = round((sum(confidence_values) / max(len(confidence_values), 1)) * 100, 2)
    approved_count = sum(1 for el in all_elements if str(getattr(el, "status", "")).lower() == "approved")
    approval_score = round((approved_count / max(len(all_elements), 1)) * 100, 2)
    with_evidence_count = sum(
        1 for el in all_elements
        if (hasattr(el, "source_evidence") and getattr(el, "source_evidence", None))
        or (hasattr(el, "evidence") and getattr(el, "evidence", None))
    )
    coverage_score = round((with_evidence_count / max(len(all_elements), 1)) * 100, 2)

    updated_at = getattr(version, "updated_at", None)
    freshness_score = 80.0
    if updated_at:
        try:
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            age_days = max((datetime.now(timezone.utc) - updated_at).days, 0)
            freshness_score = max(20.0, round(100.0 - (age_days * 2.0), 2))
        except Exception:
            freshness_score = 80.0

    overall_score = round(
        (confidence_score * 0.45) + (approval_score * 0.25) + (coverage_score * 0.2) + (freshness_score * 0.1),
        2,
    )
    response: Dict[str, Any] = {
        "overall_score": overall_score,
        "confidence_score": confidence_score,
        "approval_score": approval_score,
        "coverage_score": coverage_score,
        "freshness_score": freshness_score,
        "element_count": len(all_elements),
        "approved_count": approved_count,
    }
    if selected:
        response["selected_element"] = selected
    # Per-type diagnostics help agent developers reason about data quality.
    type_diagnostics = []
    for label, items in (
        ("entities", classes),
        ("relationships", relationships),
        ("attributes", attributes),
    ):
        if not items:
            type_diagnostics.append(
                {"type": label, "count": 0, "avg_confidence_score": 0.0, "approved_ratio": 0.0}
            )
            continue
        avg_conf = (sum(float(getattr(it, "confidence_score", 0) or 0) for it in items) / len(items)) * 100
        approved = sum(1 for it in items if str(getattr(it, "status", "")).lower() == "approved")
        type_diagnostics.append(
            {
                "type": label,
                "count": len(items),
                "avg_confidence_score": round(avg_conf, 2),
                "approved_ratio": round((approved / len(items)) * 100, 2),
            }
        )
    response["type_diagnostics"] = type_diagnostics
    return response


def _tokenize_query(value: str) -> List[str]:
    return [t for t in "".join(ch if ch.isalnum() else " " for ch in value.lower()).split() if t]


# --- Projects ---

@router.post("/projects", response_model=APIResponse)
async def create_project(request: CreateProjectRequest):
    """Create a new ontology project."""
    try:
        proj = persistence.create_project(
            name=request.name,
            description=request.description,
            domain=request.domain,
        )
        register_project_owner(proj.id, proj.name)
        return APIResponse(
            success=True,
            message="Project created",
            data=proj.model_dump(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/from-fabric", response_model=APIResponse)
async def create_project_from_fabric(request: CreateProjectFromFabricRequest):
    """Create ontology project from an existing knowledge fabric."""
    try:
        fabric_store.initialize()
        fabric = fabric_store.get(request.fabric_id)
        if not fabric:
            raise HTTPException(status_code=404, detail="Knowledge fabric not found")

        fabric_name = fabric.get("name") or request.fabric_id
        project_name = (request.name or f"{fabric_name} Ontology").strip()
        merged_description = request.description or (
            f"Ontology project bootstrapped from Knowledge Fabric '{fabric_name}' "
            f"(id: {request.fabric_id}, source_type: {fabric.get('source_type', 'unknown')})."
        )
        if "(id:" not in merged_description:
            merged_description = (
                f"{merged_description.rstrip()} "
                f"(id: {request.fabric_id}, source_type: {fabric.get('source_type', 'unknown')})."
            )
        proj = persistence.create_project(
            name=project_name,
            description=merged_description,
            domain=request.domain,
        )
        register_project_owner(proj.id, proj.name)
        linked_artifacts: List[SourceArtifact] = []
        processed_files = fabric.get("processed_files") if isinstance(fabric.get("processed_files"), list) else []
        candidate_roots = [
            getattr(settings, "ONTOLOGY_UPLOAD_DIR", None) or os.path.join(settings.ONTOLOGY_DATA_DIR, "uploads"),
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
                linked_artifacts.append(
                    SourceArtifact(
                        id=f"art_{uuid.uuid4().hex[:12]}",
                        file_name=file_name,
                        file_path=os.path.abspath(file_path),
                        source_type=_source_type_from_name(file_name, fallback="xml"),
                        project_id=proj.id,
                        ingestion_time=datetime.utcnow(),
                        metadata={"fabric_id": request.fabric_id, "linked_from": "processed_files"},
                    )
                )
                break

        if not linked_artifacts:
            materialized_path = _materialize_fabric_documents_to_xml(request.fabric_id)
            if materialized_path and os.path.isfile(materialized_path):
                file_name = os.path.basename(materialized_path)
                linked_artifacts.append(
                    SourceArtifact(
                        id=f"art_{uuid.uuid4().hex[:12]}",
                        file_name=file_name,
                        file_path=os.path.abspath(materialized_path),
                        source_type="xml",
                        project_id=proj.id,
                        ingestion_time=datetime.utcnow(),
                        metadata={"fabric_id": request.fabric_id, "linked_from": "vector_documents"},
                    )
                )

        if linked_artifacts:
            persistence.add_artifacts_to_project(proj.id, linked_artifacts)
            refreshed = persistence.get_project(proj.id)
            if refreshed is not None:
                proj = refreshed

        return APIResponse(
            success=True,
            message="Project created from knowledge fabric",
            data={
                **proj.model_dump(),
                "fabric_reference": {
                    "fabric_id": request.fabric_id,
                    "fabric_name": fabric_name,
                    "source_type": fabric.get("source_type"),
                    "document_count": fabric.get("document_count"),
                },
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects", response_model=APIResponse)
async def list_projects():
    """List all ontology projects."""
    try:
        projects = persistence.list_projects()
        allowed = allowed_project_ids()
        if allowed is not None:
            projects = [p for p in projects if p.id in allowed]
        return APIResponse(
            success=True,
            message="Projects retrieved",
            data=[p.model_dump() for p in projects],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}", response_model=APIResponse)
async def get_project(project_id: str):
    """Get project by ID."""
    if not user_owns_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    proj = persistence.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return APIResponse(success=True, message="OK", data=proj.model_dump())


@router.delete("/projects/{project_id}", response_model=APIResponse)
@router.post("/projects/{project_id}/delete", response_model=APIResponse)
async def delete_project(project_id: str):
    """Delete an ontology project and its versions/runs. Supports DELETE and POST (for proxies that block DELETE)."""
    if not user_owns_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    if not persistence.delete_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return APIResponse(success=True, message="Project deleted", data={"id": project_id})


# --- Source artifacts (ontology-only uploads; not shared with Knowledge Fabric) ---

ALLOWED_ONTOLOGY_EXTENSIONS = {".pdf", ".xml", ".docx", ".png", ".jpg", ".jpeg", ".gif", ".webp"}


@router.post("/upload", response_model=APIResponse)
async def upload_ontology_documents(files: List[UploadFile] = File(...)):
    """Upload PDF, Word (DOCX), XML, or image files for ontology discovery. Stored in ontology upload dir only."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    results = []
    upload_dir = artifact_loader.upload_dir
    os.makedirs(upload_dir, exist_ok=True)
    for file in files:
        try:
            name = file.filename or "unnamed"
            ext = os.path.splitext(name)[1].lower()
            if ext not in ALLOWED_ONTOLOGY_EXTENSIONS:
                results.append({"file": name, "status": "error", "message": f"Allowed: PDF, DOCX, XML, PNG, JPG, GIF, WEBP (got {ext})"})
                continue
            unique_name = f"{uuid.uuid4().hex}{ext}"
            file_path = os.path.join(upload_dir, unique_name)
            async with aiofiles.open(file_path, "wb") as f:
                content = await file.read()
                await f.write(content)
            results.append({
                "file": name,
                "status": "success",
                "saved_as": unique_name,
                "name": unique_name,
                "path": file_path,
            })
        except Exception as e:
            results.append({"file": file.filename, "status": "error", "message": str(e)})
    return APIResponse(
        success=True,
        message="Upload complete",
        data={"results": results, "total": len(files)},
    )


@router.get("/artifacts/available", response_model=APIResponse)
async def get_available_artifacts():
    """List files in ontology upload directory only (PDF, DOCX, XML, images). Not from Knowledge Fabric uploads."""
    files = artifact_loader.get_available_files()
    return APIResponse(success=True, message="OK", data=files)


# --- Discovery ---

@router.post("/projects/{project_id}/discover", response_model=APIResponse)
async def discover_ontology(project_id: str, request: DiscoverOntologyRequest):
    """Start ontology discovery run for a project (background)."""
    if request.project_id is not None and request.project_id != project_id:
        raise HTTPException(status_code=400, detail="project_id mismatch")
    proj = persistence.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        artifact_ids = list(request.artifact_ids or [])
        if not artifact_ids:
            artifact_ids = _ensure_fabric_artifacts_for_project(proj)
        if not artifact_ids:
            raise HTTPException(
                status_code=400,
                detail="No source artifacts available for discovery. Upload artifacts or link a knowledge fabric source."
            )
        run = persistence.create_run(project_id, artifact_ids)
        orchestrator = DiscoveryOrchestrator()

        def run_sync():
            orchestrator.run_discovery(
                run.id,
                project_id,
                artifact_ids,
                use_llm=request.use_llm,
                max_artifacts_per_run=request.max_artifacts_per_run,
                max_chunks_for_llm=request.max_chunks_for_llm,
            )

        t = threading.Thread(target=run_sync)
        t.daemon = True
        t.start()
        return APIResponse(
            success=True,
            message="Discovery started",
            data={
                "run_id": run.id,
                "project_id": project_id,
                "status": run.status.value,
                "artifact_ids": artifact_ids,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/runs", response_model=APIResponse)
async def list_runs(project_id: str):
    """List all discovery runs for this project (history), newest first."""
    runs = persistence.list_runs_for_project(project_id)
    return APIResponse(success=True, message="OK", data=runs)


@router.get("/projects/{project_id}/runs/{run_id}", response_model=APIResponse)
async def get_run(project_id: str, run_id: str):
    """Get discovery run status and result."""
    run = persistence.get_run(run_id)
    if not run or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return APIResponse(
        success=True,
        message="OK",
        data=run.model_dump(),
    )


# --- Versions ---

@router.get("/projects/{project_id}/versions", response_model=APIResponse)
async def list_versions(project_id: str):
    """List ontology versions for a project."""
    versions = persistence.list_versions_for_project(project_id)
    return APIResponse(success=True, message="OK", data=versions)


@router.get("/projects/{project_id}/versions/{version_id}", response_model=APIResponse)
async def get_version(project_id: str, version_id: str):
    """Get ontology version by ID."""
    version = persistence.get_version(version_id)
    if not version or version.project_id != project_id:
        raise HTTPException(status_code=404, detail="Version not found")
    data = {
        "id": version.id,
        "project_id": version.project_id,
        "version_label": version.version_label,
        "is_draft": version.is_draft,
        "classes": [c.model_dump() for c in version.classes],
        "relationships": [r.model_dump() for r in version.relationships],
        "attributes": [a.model_dump() for a in version.attributes],
        "constraints": [c.model_dump() for c in version.constraints],
        "created_at": version.created_at.isoformat() if version.created_at else None,
        "updated_at": version.updated_at.isoformat() if version.updated_at else None,
    }
    return APIResponse(success=True, message="OK", data=data)


# --- Review: update class / relationship / attribute ---

@router.put("/classes/{class_id}", response_model=APIResponse)
async def update_class(class_id: str, body: OntologyClassUpdate):
    """Update an ontology class (find in any version and update in place)."""
    # Persistence is file-based per version; we need to find which version has this class
    for proj in persistence.list_projects():
        for v_meta in persistence.list_versions_for_project(proj.id):
            version = persistence.get_version(v_meta["id"])
            if not version:
                continue
            for c in version.classes:
                if c.id == class_id:
                    if body.name is not None:
                        c.name = body.name
                    if body.normalized_name is not None:
                        c.normalized_name = body.normalized_name
                    if body.definition is not None:
                        c.definition = body.definition
                    if body.aliases is not None:
                        c.aliases = body.aliases
                    if body.status is not None:
                        try:
                            c.status = OntologyElementStatus(body.status)
                        except ValueError:
                            pass
                    persistence.save_version(version)
                    return APIResponse(success=True, message="Class updated", data=c.model_dump())
    raise HTTPException(status_code=404, detail="Class not found")


@router.put("/relationships/{rel_id}", response_model=APIResponse)
async def update_relationship(rel_id: str, body: OntologyRelationshipUpdate):
    """Update an ontology relationship."""
    for proj in persistence.list_projects():
        for v_meta in persistence.list_versions_for_project(proj.id):
            version = persistence.get_version(v_meta["id"])
            if not version:
                continue
            for r in version.relationships:
                if r.id == rel_id:
                    if body.relationship_name is not None:
                        r.relationship_name = body.relationship_name
                    if body.definition is not None:
                        r.definition = body.definition
                    if body.cardinality_if_detected is not None:
                        r.cardinality_if_detected = body.cardinality_if_detected
                    if body.status is not None:
                        try:
                            r.status = OntologyElementStatus(body.status)
                        except ValueError:
                            pass
                    persistence.save_version(version)
                    return APIResponse(success=True, message="Relationship updated", data=r.model_dump())
    raise HTTPException(status_code=404, detail="Relationship not found")


@router.put("/attributes/{attr_id}", response_model=APIResponse)
async def update_attribute(attr_id: str, body: OntologyAttributeUpdate):
    """Update an ontology attribute."""
    for proj in persistence.list_projects():
        for v_meta in persistence.list_versions_for_project(proj.id):
            version = persistence.get_version(v_meta["id"])
            if not version:
                continue
            for a in version.attributes:
                if a.id == attr_id:
                    if body.attribute_name is not None:
                        a.attribute_name = body.attribute_name
                    if body.normalized_name is not None:
                        a.normalized_name = body.normalized_name
                    if body.data_type_guess is not None:
                        a.data_type_guess = body.data_type_guess
                    if body.required_flag_guess is not None:
                        a.required_flag_guess = body.required_flag_guess
                    if body.description is not None:
                        a.description = body.description
                    if body.status is not None:
                        try:
                            a.status = OntologyElementStatus(body.status)
                        except ValueError:
                            pass
                    persistence.save_version(version)
                    return APIResponse(success=True, message="Attribute updated", data=a.model_dump())
    raise HTTPException(status_code=404, detail="Attribute not found")


# --- Review: approve / reject / merge ---

@router.post("/review/approve", response_model=APIResponse)
async def review_approve(body: ReviewApproveRequest):
    """Approve ontology elements."""
    version = persistence.get_version(body.version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    updated = 0
    for elem_type in [body.element_type]:
        if elem_type == "class":
            for c in version.classes:
                if c.id in body.element_ids:
                    c.status = OntologyElementStatus.APPROVED
                    updated += 1
        elif elem_type == "relationship":
            for r in version.relationships:
                if r.id in body.element_ids:
                    r.status = OntologyElementStatus.APPROVED
                    updated += 1
        elif elem_type == "attribute":
            for a in version.attributes:
                if a.id in body.element_ids:
                    a.status = OntologyElementStatus.APPROVED
                    updated += 1
    persistence.save_version(version)
    return APIResponse(success=True, message=f"Approved {updated} element(s)", data={"updated": updated})


@router.post("/review/reject", response_model=APIResponse)
async def review_reject(body: ReviewRejectRequest):
    """Reject ontology elements."""
    version = persistence.get_version(body.version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    updated = 0
    for c in version.classes:
        if c.id in body.element_ids:
            c.status = OntologyElementStatus.REJECTED
            updated += 1
    for r in version.relationships:
        if r.id in body.element_ids:
            r.status = OntologyElementStatus.REJECTED
            updated += 1
    for a in version.attributes:
        if a.id in body.element_ids:
            a.status = OntologyElementStatus.REJECTED
            updated += 1
    persistence.save_version(version)
    return APIResponse(success=True, message=f"Rejected {updated} element(s)", data={"updated": updated})


@router.post("/merge", response_model=APIResponse)
async def merge_entities(body: MergeRequest):
    """Merge duplicate entities into target."""
    version = persistence.get_version(body.version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    target_id = body.target_class_id
    to_remove = [id for id in body.source_class_ids if id != target_id]
    # Re-point relationships and attributes to target; then remove source classes
    for r in version.relationships:
        if r.source_class_id in to_remove:
            r.source_class_id = target_id
        if r.target_class_id in to_remove:
            r.target_class_id = target_id
    for a in version.attributes:
        if a.class_id in to_remove:
            a.class_id = target_id
    version.classes = [c for c in version.classes if c.id not in to_remove]
    persistence.save_version(version)
    return APIResponse(
        success=True,
        message=f"Merged {len(to_remove)} into {target_id}",
        data={"merged_count": len(to_remove), "target_id": target_id},
    )


# --- Export ---

@router.get("/export/{version_id}")
async def export_ontology(
    version_id: str,
    format: str = Query("json", alias="format"),
):
    """Export ontology version as JSON, CSV, or graph schema."""
    version = persistence.get_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    if format == "json":
        return APIResponse(success=True, message="OK", data=export_service.export_json(version))
    if format == "csv":
        return PlainTextResponse(
            export_service.export_csv(version),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=ontology_{version_id}.csv"},
        )
    if format == "graph":
        return APIResponse(success=True, message="OK", data=export_service.export_graph(version))
    raise HTTPException(status_code=400, detail="format must be json, csv, or graph")


@router.get("/export/{version_id}/canonical", response_model=APIResponse)
async def export_canonical(version_id: str):
    """Get canonical data model for a version."""
    version = persistence.get_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return APIResponse(success=True, message="OK", data=export_service.canonical_model(version))


# --- Enrichment / governance / candidate queue ---


@router.post("/enrichment/discover", response_model=APIResponse)
async def enrichment_discover(request: EnrichmentDiscoverRequest):
    """Discover ontology enrichment candidates from dataset schema fields."""
    try:
        candidates = enrichment_service.discover_candidates(
            source_dataset_id=request.source_dataset_id,
            fields=request.fields,
            metadata=request.metadata,
            created_by=request.created_by,
        )
        return APIResponse(success=True, message="Discovery completed", data=[c.model_dump() for c in candidates])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enrichment/discover-from-project", response_model=APIResponse)
async def enrichment_discover_from_project(request: EnrichmentDiscoverFromProjectRequest):
    """Generate enrichment candidates from an existing ontology project/version."""
    project = persistence.get_project(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    version_id = request.version_id
    if not version_id:
        versions = persistence.list_versions_for_project(request.project_id)
        if not versions:
            raise HTTPException(status_code=400, detail="Project has no ontology versions")
        versions_sorted = sorted(versions, key=lambda v: str(v.get("created_at", "")), reverse=True)
        version_id = versions_sorted[0].get("id")
    version = persistence.get_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    fields: List[Dict[str, Any]] = []
    for a in version.attributes:
        fields.append(
            {
                "name": a.attribute_name,
                "type": a.data_type_guess or "string",
                "sample_values": [],
            }
        )
    # If attributes are sparse, derive from class names too.
    if not fields:
        for c in version.classes:
            fields.append({"name": c.normalized_name, "type": "entity", "sample_values": []})
    source_dataset_id = f"ontology_project_{request.project_id}_version_{version_id}"
    metadata = {
        "source_type": "ontology_project",
        "project_id": request.project_id,
        "project_name": project.name,
        "version_id": version_id,
    }
    try:
        candidates = enrichment_service.discover_candidates(
            source_dataset_id=source_dataset_id,
            fields=fields,
            metadata=metadata,
            created_by=request.created_by,
        )
        return APIResponse(success=True, message="Discovery from project completed", data=[c.model_dump() for c in candidates])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/enrichment/candidates", response_model=APIResponse)
async def list_enrichment_candidates():
    candidates = persistence.list_candidates()
    return APIResponse(success=True, message="OK", data=[c.model_dump() for c in candidates])


@router.get("/enrichment/candidates/{candidate_id}", response_model=APIResponse)
async def get_enrichment_candidate(candidate_id: str):
    candidate = persistence.get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    policy_logs = [p.model_dump() for p in persistence.list_policy_decisions(candidate_id)]
    return APIResponse(success=True, message="OK", data={"candidate": candidate.model_dump(), "policy_logs": policy_logs})


@router.post("/enrichment/candidates/{candidate_id}/approve", response_model=APIResponse)
async def approve_candidate(candidate_id: str, body: CandidateReviewRequest):
    updated = persistence.update_candidate_status(candidate_id, ChangeStatus.APPROVED.value, body.reviewer, body.notes)
    if not updated:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return APIResponse(success=True, message="Candidate approved", data=updated.model_dump())


@router.post("/enrichment/candidates/{candidate_id}/reject", response_model=APIResponse)
async def reject_candidate(candidate_id: str, body: CandidateReviewRequest):
    updated = persistence.update_candidate_status(candidate_id, ChangeStatus.REJECTED.value, body.reviewer, body.notes)
    if not updated:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return APIResponse(success=True, message="Candidate rejected", data=updated.model_dump())


@router.post("/enrichment/candidates/{candidate_id}/request-evidence", response_model=APIResponse)
async def request_candidate_evidence(candidate_id: str, body: CandidateReviewRequest):
    updated = persistence.update_candidate_status(candidate_id, ChangeStatus.NEEDS_MORE_EVIDENCE.value, body.reviewer, body.notes)
    if not updated:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return APIResponse(success=True, message="Candidate marked for more evidence", data=updated.model_dump())


@router.post("/enrichment/candidates/{candidate_id}/promote", response_model=APIResponse)
async def promote_candidate(candidate_id: str, body: CandidateReviewRequest):
    candidate = persistence.get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.status not in {ChangeStatus.APPROVED, ChangeStatus.AUTO_APPLIED, ChangeStatus.PENDING_APPROVAL}:
        raise HTTPException(status_code=400, detail="Candidate must be approved or auto-applied before promotion")
    snapshot = persistence.get_current_ontology_snapshot()
    attrs = snapshot.get("attributes", [])
    rels = snapshot.get("relationships", [])
    entities = snapshot.get("entities", [])
    if candidate.suggestedEntity and not any(e.get("name") == candidate.suggestedEntity for e in entities):
        entities.append({"id": f"ent_{uuid.uuid4().hex[:10]}", "name": candidate.suggestedEntity, "class_name": candidate.suggestedEntity})
    if candidate.suggestedAttribute:
        attrs.append(
            {
                "id": f"attr_{uuid.uuid4().hex[:10]}",
                "name": candidate.suggestedAttribute,
                "entity": candidate.suggestedEntity or "GenericEntity",
                "sensitivity": candidate.sensitivity.value if hasattr(candidate.sensitivity, "value") else str(candidate.sensitivity),
            }
        )
    if candidate.suggestedRelationship:
        rels.append({"id": f"rel_{uuid.uuid4().hex[:10]}", "name": candidate.suggestedRelationship})
    snapshot["entities"] = entities
    snapshot["attributes"] = attrs
    snapshot["relationships"] = rels
    persistence.upsert_ontology_snapshot(snapshot)
    version = persistence.create_version_record(
        change_ids=[candidate_id],
        summary=f"Promoted candidate {candidate_id}: {candidate.changeType}",
        approved_by=body.reviewer,
        environment="draft",
        snapshot=snapshot,
    )
    updated = persistence.update_candidate_status(candidate_id, ChangeStatus.PROMOTED.value, body.reviewer, body.notes)
    return APIResponse(
        success=True,
        message="Candidate promoted",
        data={"candidate": updated.model_dump() if updated else None, "version": version.model_dump()},
    )


@router.post("/enrichment/policy/evaluate", response_model=APIResponse)
async def evaluate_policy(candidate: Dict[str, Any]):
    mode = persistence.get_governance_mode()
    obj = persistence.get_candidate(candidate.get("id")) if candidate.get("id") else None
    if obj:
        decision = obj.policyDecision.value if hasattr(obj.policyDecision, "value") else str(obj.policyDecision)
        return APIResponse(success=True, message="Existing policy decision", data={"mode": mode.value, "decision": decision})
    return APIResponse(success=True, message="Policy evaluation unavailable for transient candidate", data={"mode": mode.value})


@router.get("/versions", response_model=APIResponse)
async def list_ontology_versions():
    persistence.ensure_timeline_baseline_if_empty()
    versions = persistence.list_version_records()
    return APIResponse(success=True, message="OK", data=[v.model_dump() for v in versions])


@router.get("/versions/{version_id}", response_model=APIResponse)
async def get_ontology_version(version_id: str):
    version = persistence.get_version_record(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return APIResponse(success=True, message="OK", data=version.model_dump())


@router.post("/versions/{version_id}/rollback", response_model=APIResponse)
async def rollback_ontology_version(version_id: str, body: CandidateReviewRequest):
    target = persistence.get_version_record(version_id)
    if not target:
        raise HTTPException(status_code=404, detail="Version not found")
    persistence.upsert_ontology_snapshot(target.snapshot)
    rollback_version = persistence.create_version_record(
        change_ids=target.changeIds,
        summary=f"Rollback to {target.versionNumber}",
        approved_by=body.reviewer,
        environment=target.environment.value if hasattr(target.environment, "value") else str(target.environment),
        rollback_reference=target.id,
        snapshot=target.snapshot,
    )
    return APIResponse(success=True, message="Rollback completed", data=rollback_version.model_dump())


@router.get("/compare", response_model=APIResponse)
async def compare_versions(fromVersion: str = Query(...), toVersion: str = Query(...)):
    persistence.ensure_timeline_baseline_if_empty()
    frm = persistence.get_version_record(fromVersion)
    to = persistence.get_version_record(toVersion)
    if not frm or not to:
        raise HTTPException(status_code=404, detail="Version not found")
    from_attrs = {(a.get("entity"), a.get("name")) for a in frm.snapshot.get("attributes", []) if isinstance(a, dict)}
    to_attrs = {(a.get("entity"), a.get("name")) for a in to.snapshot.get("attributes", []) if isinstance(a, dict)}
    added_attrs = list(to_attrs - from_attrs)
    removed_attrs = list(from_attrs - to_attrs)
    from_entities = {e.get("name") for e in frm.snapshot.get("entities", []) if isinstance(e, dict)}
    to_entities = {e.get("name") for e in to.snapshot.get("entities", []) if isinstance(e, dict)}
    added_entities = sorted(to_entities - from_entities)
    removed_entities = sorted(from_entities - to_entities)
    from_rels = {r.get("name") for r in frm.snapshot.get("relationships", []) if isinstance(r, dict)}
    to_rels = {r.get("name") for r in to.snapshot.get("relationships", []) if isinstance(r, dict)}
    added_relationships = sorted(to_rels - from_rels)
    removed_relationships = sorted(from_rels - to_rels)
    return APIResponse(
        success=True,
        message="OK",
        data={
            "fromVersion": fromVersion,
            "toVersion": toVersion,
            "summary": {
                "attributes_added": len(added_attrs),
                "attributes_removed": len(removed_attrs),
                "entities_added": len(added_entities),
                "entities_removed": len(removed_entities),
                "relationships_added": len(added_relationships),
                "relationships_removed": len(removed_relationships),
            },
            "added_attributes": [{"entity": a[0], "name": a[1]} for a in added_attrs],
            "removed_attributes": [{"entity": a[0], "name": a[1]} for a in removed_attrs],
            "added_entities": [{"name": n} for n in added_entities],
            "removed_entities": [{"name": n} for n in removed_entities],
            "added_relationships": [{"name": n} for n in added_relationships],
            "removed_relationships": [{"name": n} for n in removed_relationships],
        },
    )


@router.get("/settings/governance-mode", response_model=APIResponse)
async def get_governance_mode():
    mode = persistence.get_governance_mode()
    return APIResponse(success=True, message="OK", data={"mode": mode.value})


@router.put("/settings/governance-mode", response_model=APIResponse)
async def update_governance_mode(request: GovernanceModeUpdateRequest):
    updated = persistence.set_governance_mode(request.mode, request.updated_by)
    return APIResponse(success=True, message="Governance mode updated", data=updated)


@router.post("/agent/query", response_model=APIResponse)
async def agent_query_playground(request: AgentQueryRequest):
    """Run an agent-style query with generated query, evidence, and trust score."""
    version = persistence.get_version(request.version_id)
    if not version or version.project_id != request.project_id:
        raise HTTPException(status_code=404, detail="Version not found for project")

    query_text = request.query.strip().lower()
    query_tokens = _tokenize_query(query_text)
    if not query_text:
        raise HTTPException(status_code=400, detail="query cannot be empty")

    classes = getattr(version, "classes", []) or []
    relationships = getattr(version, "relationships", []) or []
    attributes = getattr(version, "attributes", []) or []

    ranked: List[Dict[str, Any]] = []
    for c in classes:
        name = (getattr(c, "normalized_name", "") or "").lower()
        definition = (getattr(c, "definition", "") or "").lower()
        score = 0
        if query_text in name:
            score += 0.8
        if query_text in definition:
            score += 0.4
        token_hits = sum(1 for token in query_tokens if token in name or token in definition)
        score += min(0.35, token_hits * 0.07)
        score += min(0.2, float(getattr(c, "confidence_score", 0) or 0) * 0.2)
        if score > 0:
            ranked.append({"type": "entity", "id": c.id, "name": getattr(c, "normalized_name", c.id), "score": round(score, 3), "obj": c})
    for a in attributes:
        name = (getattr(a, "attribute_name", "") or "").lower()
        desc = (getattr(a, "description", "") or "").lower()
        score = 0
        if query_text in name:
            score += 0.7
        if query_text in desc:
            score += 0.3
        token_hits = sum(1 for token in query_tokens if token in name or token in desc)
        score += min(0.35, token_hits * 0.07)
        score += min(0.2, float(getattr(a, "confidence_score", 0) or 0) * 0.2)
        if score > 0:
            ranked.append({"type": "attribute", "id": a.id, "name": getattr(a, "attribute_name", a.id), "score": round(score, 3), "obj": a})
    for r in relationships:
        rel_name = (getattr(r, "relationship_name", "") or "").lower()
        score = 0
        if query_text in rel_name:
            score += 0.75
        token_hits = sum(1 for token in query_tokens if token in rel_name)
        score += min(0.35, token_hits * 0.09)
        score += min(0.2, float(getattr(r, "confidence_score", 0) or 0) * 0.2)
        if score > 0:
            ranked.append({"type": "relationship", "id": r.id, "name": getattr(r, "relationship_name", r.id), "score": round(score, 3), "obj": r})

    ranked = sorted(ranked, key=lambda x: x["score"], reverse=True)[: max(1, request.top_k)]
    evidence_bundle: List[Dict[str, Any]] = []
    for item in ranked:
        obj = item["obj"]
        evidence = []
        if hasattr(obj, "source_evidence") and getattr(obj, "source_evidence", None):
            evidence = [ev.model_dump() if hasattr(ev, "model_dump") else ev for ev in getattr(obj, "source_evidence", [])[:3]]
        elif hasattr(obj, "evidence") and getattr(obj, "evidence", None):
            evidence = [ev.model_dump() if hasattr(ev, "model_dump") else ev for ev in getattr(obj, "evidence", [])[:3]]
        evidence_bundle.append(
            {
                "element_id": item["id"],
                "element_type": item["type"],
                "element_name": item["name"],
                "rank_score": item["score"],
                "citations": evidence,
                "provenance": {
                    "project_id": request.project_id,
                    "version_id": request.version_id,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "pipeline": "ontology-discovery",
                },
            }
        )

    generated_query = {
        "mode": "keyword+ontology",
        "query": request.query,
        "filters": {"role": request.role, "top_k": request.top_k},
    }
    top_names = [str(item.get("name", "")) for item in ranked[:3] if item.get("name")]
    if evidence_bundle:
        if top_names:
            answer_preview = (
                f"Matched {len(evidence_bundle)} ontology elements. "
                f"Top matches: {', '.join(top_names)}."
            )
        else:
            answer_preview = f"Matched {len(evidence_bundle)} ontology elements for '{request.query}'."
    else:
        answer_preview = (
            f"No direct ontology matches found for '{request.query}'. "
            "Try entity/attribute keywords or increase result depth."
        )
    trust = _compute_trust_score(version)
    state = _load_agent_utils_state()
    state["query_logs"].append(
        {
            "id": uuid.uuid4().hex,
            "query": request.query,
            "project_id": request.project_id,
            "version_id": request.version_id,
            "role": request.role,
            "result_count": len(evidence_bundle),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    state["query_logs"] = state["query_logs"][-200:]
    _save_agent_utils_state(state)

    return APIResponse(
        success=True,
        message="Agent query executed",
        data={
            "answer_preview": answer_preview,
            "generated_query": generated_query,
            "results": evidence_bundle,
            "trust_score": trust,
            "debug": {
                "total_entities": len(classes),
                "total_relationships": len(relationships),
                "total_attributes": len(attributes),
                "query_tokens": query_tokens,
            } if request.include_debug else None,
        },
    )


@router.get("/agent/contracts", response_model=APIResponse)
async def list_agent_data_contracts():
    state = _load_agent_utils_state()
    contracts = sorted(
        state.get("contracts", []),
        key=lambda x: (x.get("name", ""), x.get("version", "")),
    )
    return APIResponse(success=True, message="OK", data=contracts)


@router.post("/agent/contracts", response_model=APIResponse)
async def upsert_agent_data_contract(request: AgentDataContractUpsertRequest):
    state = _load_agent_utils_state()
    contracts = state.get("contracts", [])
    payload = request.model_dump()
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    existing_idx = next(
        (
            idx
            for idx, c in enumerate(contracts)
            if c.get("contract_id") == request.contract_id and c.get("version") == request.version
        ),
        None,
    )
    if existing_idx is None:
        payload["created_at"] = payload["updated_at"]
        contracts.append(payload)
        message = "Contract created"
    else:
        payload["created_at"] = contracts[existing_idx].get("created_at", payload["updated_at"])
        contracts[existing_idx] = payload
        message = "Contract updated"
    state["contracts"] = contracts
    _save_agent_utils_state(state)
    return APIResponse(success=True, message=message, data=payload)


def _match_contract_record(c: Dict[str, Any], contract_id: str, version: str) -> bool:
    cid = str(c.get("contract_id", "")).strip()
    ver = str(c.get("version", "")).strip()
    return cid == contract_id.strip() and ver == version.strip()


def _delete_agent_contract_from_state(contract_id: str, version: str) -> Dict[str, str]:
    state = _load_agent_utils_state()
    contracts = state.get("contracts", [])
    before = len(contracts)
    filtered = [c for c in contracts if not _match_contract_record(c, contract_id, version)]
    if len(filtered) == before:
        raise HTTPException(status_code=404, detail="Contract not found")
    state["contracts"] = filtered
    _save_agent_utils_state(state)
    return {"contract_id": contract_id.strip(), "version": version.strip()}


@router.post("/agent/contracts/delete", response_model=APIResponse)
async def delete_agent_data_contract_post(request: AgentDataContractDeleteRequest):
    """Remove a contract (POST mirrors /projects/{id}/delete — works reliably behind SPA proxies)."""
    data = _delete_agent_contract_from_state(request.contract_id, request.version)
    return APIResponse(success=True, message="Contract deleted", data=data)


@router.delete("/agent/contracts/{contract_id}", response_model=APIResponse)
async def delete_agent_data_contract(contract_id: str, version: str = Query(..., description="Semver contract version")):
    data = _delete_agent_contract_from_state(contract_id, version)
    return APIResponse(success=True, message="Contract deleted", data=data)


@router.get("/agent/trust-score/{project_id}/{version_id}", response_model=APIResponse)
async def get_agent_trust_score(project_id: str, version_id: str, element_id: Optional[str] = Query(None)):
    version = persistence.get_version(version_id)
    if not version or version.project_id != project_id:
        raise HTTPException(status_code=404, detail="Version not found for project")

    selected = None
    if element_id:
        for collection, element_type in (
            (getattr(version, "classes", []) or [], "entity"),
            (getattr(version, "relationships", []) or [], "relationship"),
            (getattr(version, "attributes", []) or [], "attribute"),
        ):
            for el in collection:
                if getattr(el, "id", None) == element_id:
                    selected = {
                        "id": element_id,
                        "type": element_type,
                        "name": getattr(el, "normalized_name", None)
                        or getattr(el, "relationship_name", None)
                        or getattr(el, "attribute_name", None)
                        or element_id,
                        "confidence_score": round(float(getattr(el, "confidence_score", 0) or 0) * 100, 2),
                        "status": str(getattr(el, "status", "")),
                    }
                    break
            if selected:
                break

    trust = _compute_trust_score(version, selected=selected)
    return APIResponse(success=True, message="OK", data=trust)


@router.post("/agent/policy/evaluate", response_model=APIResponse)
async def evaluate_agent_policy(request: AgentPolicyEvaluateRequest):
    payload = request.payload or {}
    role = request.role.lower()
    purpose = (request.purpose or "general").lower()
    masked_fields = []
    risk_flags = []
    redacted = dict(payload)
    purpose_blocklist = {
        "analytics": {"patient_id", "member_id", "ssn", "dob", "address", "phone", "email"},
        "testing": {"ssn"},
        "general": {"ssn"},
    }
    blocked_for_purpose = purpose_blocklist.get(purpose, set())

    for field in list(redacted.keys()):
        lower_field = field.lower()
        is_sensitive = any(token in lower_field for token in ["ssn", "dob", "phone", "email", "address", "member_id", "patient_id"])
        purpose_blocked = lower_field in blocked_for_purpose
        if is_sensitive:
            risk_flags.append({"field": field, "reason": "sensitive_identifier"})
            if role not in {"admin", "steward"}:
                redacted[field] = "***masked***"
                masked_fields.append(field)
        if purpose_blocked:
            risk_flags.append({"field": field, "reason": f"blocked_for_purpose:{purpose}"})
            redacted[field] = "***masked***"
            if field not in masked_fields:
                masked_fields.append(field)
    denied_reasons: List[str] = []
    if request.strict_mode and len(masked_fields) > 0:
        denied_reasons.append("strict_mode_sensitive_data")
    if any(flag["reason"].startswith("blocked_for_purpose:") for flag in risk_flags):
        denied_reasons.append("purpose_restriction")
    allowed = len(denied_reasons) == 0
    return APIResponse(
        success=True,
        message="Policy evaluated",
        data={
            "allowed": allowed,
            "role": request.role,
            "purpose": request.purpose,
            "masked_fields": masked_fields,
            "risk_flags": risk_flags,
            "output_payload": redacted,
            "policy_mode": "strict" if request.strict_mode else "standard",
            "denied_reasons": denied_reasons,
        },
    )


def _class_id_to_name(class_id: str, classes: List[Any]) -> str:
    for c in classes or []:
        if getattr(c, "id", None) == class_id:
            return getattr(c, "normalized_name", class_id)
    return class_id


def _build_ontology_chat_system_prompt(
    version: Optional[Any],
    context: Optional[Dict[str, Any]],
) -> str:
    """Build a short system prompt for ontology Q&A to minimize tokens."""
    parts = [
        "You help users understand a domain ontology. Answer briefly (1-3 sentences). "
        "Use only the ontology context below.",
    ]
    if version:
        classes = getattr(version, "classes", []) or []
        relationships = getattr(version, "relationships", []) or []
        attributes = getattr(version, "attributes", []) or []
        if classes:
            names = [getattr(c, "normalized_name", str(c)) for c in classes[:12]]
            parts.append(f"\nEntities: {', '.join(names)}")
        if relationships:
            rels = []
            for r in relationships[:8]:
                src = _class_id_to_name(getattr(r, "source_class_id", "") or "", classes)
                tgt = _class_id_to_name(getattr(r, "target_class_id", "") or "", classes)
                name = getattr(r, "relationship_name", "") or "?"
                rels.append(f"{src}-{name}-{tgt}")
            parts.append(f"\nRels: {'; '.join(rels)}")
        if attributes:
            attrs = [getattr(a, "attribute_name", str(a)) for a in attributes[:10]]
            parts.append(f"\nAttrs: {', '.join(str(a) for a in attrs)}")
    if context:
        sel_type = context.get("selected_type") or context.get("selectedType")
        sel_name = context.get("selected_name") or context.get("selectedName")
        sel_summary = context.get("selected_summary") or context.get("selectedSummary")
        if sel_type or sel_name:
            summary = (sel_summary or "")[:180]
            parts.append(f"\nSelected: {sel_type or '?'} {sel_name or '?'}. {summary}")
    return "".join(parts)


@router.post("/chat", response_model=APIResponse)
async def ontology_chat(request: OntologyChatRequest):
    """Real-time Q&A about the ontology using OpenAI. Requires OpenAI API key."""
    version = None
    if request.version_id:
        version = persistence.get_version(request.version_id)
    system_prompt = _build_ontology_chat_system_prompt(version, request.context)
    reply = llm_ontology.chat(
        user_message=request.message,
        system_prompt=system_prompt,
        history=request.history,
    )
    if reply is None:
        raise HTTPException(
            status_code=503,
            detail="OpenAI is not available. Configure OPENAI_API_KEY or add the key in Settings.",
        )
    return APIResponse(success=True, message="OK", data={"reply": reply})

