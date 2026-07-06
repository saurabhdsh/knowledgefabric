"""Knowledge graph build, export, and traversal APIs."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.models.knowledge import APIResponse
from app.services.graph.adapters.neo4j_adapter import neo4j_adapter
from app.services.graph.adapters.rdf_adapter import rdf_adapter
from app.services.graph.graph_materialization_service import graph_materialization_service
from app.services.graph.graph_store import graph_store
from app.services.ontology.ontology_db_repository import ontology_db_repository
from app.services.platform.fabric_store import fabric_store
from app.services.platform.job_service import job_service

router = APIRouter()


class ApproveVersionRequest(BaseModel):
    approved_by: Optional[str] = "analyst"
    trigger_graph_build: bool = True
    storage_backend: Optional[str] = None


class GraphBuildRequest(BaseModel):
    ontology_version_id: str
    storage_backend: Optional[str] = None
    async_job: bool = True


class GraphExportRequest(BaseModel):
    ontology_version_id: str
    targets: List[str] = Field(default_factory=lambda: ["rdf"])


@router.post("/ontology/versions/{version_id}/approve", response_model=APIResponse)
async def approve_ontology_version(version_id: str, body: ApproveVersionRequest):
    try:
        version = ontology_db_repository.approve_version(version_id, body.approved_by)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    fabric_id = None
    session_fabrics = fabric_store.list_all_dicts()
    for fab in session_fabrics:
        if fab.get("ontology_project_id") == version.project_id:
            fabric_id = fab["id"]
            fabric_store.link_ontology(fabric_id, version.project_id, version_id)
            break

    graph_job_id = None
    if body.trigger_graph_build and fabric_id:
        if body.storage_backend:
            backend = body.storage_backend
        else:
            backend = settings.GRAPH_STORAGE_BACKEND
        graph_job_id = job_service.enqueue(
            "graph_build",
            fabric_id,
            {"ontology_version_id": version_id, "storage_backend": backend},
        )

    return APIResponse(
        success=True,
        message="Ontology version approved",
        data={
            "version_id": version_id,
            "fabric_id": fabric_id,
            "graph_build_job_id": graph_job_id,
        },
    )


@router.post("/fabrics/{fabric_id}/graph/build", response_model=APIResponse)
async def build_graph(fabric_id: str, body: GraphBuildRequest):
    if not fabric_store.get(fabric_id):
        raise HTTPException(status_code=404, detail="Fabric not found")
    if body.async_job:
        job_id = job_service.enqueue(
            "graph_build",
            fabric_id,
            {
                "ontology_version_id": body.ontology_version_id,
                "storage_backend": body.storage_backend or settings.GRAPH_STORAGE_BACKEND,
            },
        )
        return APIResponse(success=True, message="Graph build enqueued", data={"job_id": job_id})

    result = graph_materialization_service.materialize(
        fabric_id, body.ontology_version_id, body.storage_backend
    )
    return APIResponse(success=True, message="Graph materialized", data=result)


@router.get("/fabrics/{fabric_id}/graph", response_model=APIResponse)
async def get_canonical_graph(fabric_id: str, ontology_version_id: Optional[str] = None):
    fabric = fabric_store.get(fabric_id)
    if not fabric:
        raise HTTPException(status_code=404, detail="Fabric not found")
    version_id = ontology_version_id or fabric.get("approved_ontology_version_id")
    payload = graph_store.get_graph_payload(fabric_id, version_id)
    if payload.get("node_count", 0) == 0:
        return APIResponse(
            success=True,
            message="No canonical graph yet — approve ontology and run graph build",
            data={**payload, "graph_type": "canonical"},
        )
    return APIResponse(success=True, message="Canonical graph", data={**payload, "graph_type": "canonical"})


@router.get("/fabrics/{fabric_id}/graph/neighbors/{node_id}", response_model=APIResponse)
async def get_graph_neighbors(
    fabric_id: str,
    node_id: str,
    hops: int = 1,
    ontology_version_id: Optional[str] = None,
):
    data = graph_store.get_neighbors(fabric_id, node_id, hops=hops, ontology_version_id=ontology_version_id)
    return APIResponse(success=True, message="Graph neighbors", data=data)


@router.post("/fabrics/{fabric_id}/graph/export", response_model=APIResponse)
async def export_graph(fabric_id: str, body: GraphExportRequest):
    if not fabric_store.get(fabric_id):
        raise HTTPException(status_code=404, detail="Fabric not found")
    exports: Dict[str, Any] = {}
    if "neo4j" in body.targets:
        exports["neo4j"] = neo4j_adapter.export_fabric_graph(fabric_id, body.ontology_version_id)
    if "rdf" in body.targets:
        exports["rdf"] = rdf_adapter.export_fabric_graph(fabric_id, body.ontology_version_id)
    if "stardog" in body.targets:
        exports["stardog"] = rdf_adapter.push_to_stardog(fabric_id, body.ontology_version_id)
    return APIResponse(success=True, message="Graph exported", data=exports)
