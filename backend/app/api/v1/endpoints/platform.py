"""Platform jobs and enterprise workflow APIs."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.knowledge import APIResponse
from app.services.platform.fabric_store import fabric_store
from app.services.platform.job_service import job_service

router = APIRouter()


class EnqueueJobRequest(BaseModel):
    job_type: str = Field(..., description="fabric_ingest | ontology_discovery | graph_build | graph_export")
    fabric_id: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)


class LinkOntologyRequest(BaseModel):
    project_id: str
    approved_version_id: Optional[str] = None


@router.get("/jobs/{job_id}", response_model=APIResponse)
async def get_job(job_id: str):
    job = job_service.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return APIResponse(success=True, message="Job status", data=job)


@router.get("/fabrics/{fabric_id}/jobs", response_model=APIResponse)
async def list_fabric_jobs(fabric_id: str):
    jobs = job_service.list_for_fabric(fabric_id)
    return APIResponse(success=True, message=f"{len(jobs)} job(s)", data=jobs)


@router.post("/jobs", response_model=APIResponse)
async def enqueue_job(body: EnqueueJobRequest):
    if body.job_type not in ("fabric_ingest", "ontology_discovery", "graph_build", "graph_export"):
        raise HTTPException(status_code=400, detail="Invalid job_type")
    job_id = job_service.enqueue(body.job_type, body.fabric_id, body.config)
    return APIResponse(success=True, message="Job enqueued", data={"job_id": job_id})


@router.post("/fabrics/{fabric_id}/discover-ontology", response_model=APIResponse)
async def trigger_ontology_discovery(
    fabric_id: str,
    use_llm: bool = True,
    project_id: Optional[str] = None,
):
    """Enqueue ontology discovery for a fabric.

    Tabular Release 2.0 fabrics use measured-profile schema discovery.
    Optional ``project_id`` writes the draft into the Ontology Discovery
    project the user has open (Create-from-Fabric), instead of only the
    fabric's default ``ontology_project_id``.
    """
    fabric = fabric_store.get(fabric_id)
    if not fabric:
        raise HTTPException(status_code=404, detail="Fabric not found")
    resolved_project = (
        (project_id or "").strip()
        or fabric.get("ontology_project_id")
        or f"proj_{fabric_id[-12:]}"
    )
    # Keep fabric → project linkage consistent with the project being discovered into.
    fabric["ontology_project_id"] = resolved_project
    fabric_store.save(fabric)
    job_id = job_service.enqueue_once(
        "ontology_discovery",
        fabric_id,
        {
            "project_id": resolved_project,
            "project_name": f"Ontology for {fabric.get('name', fabric_id)}",
            "use_llm": use_llm,
        },
    )
    return APIResponse(
        success=True,
        message="Ontology discovery enqueued",
        data={"job_id": job_id, "project_id": resolved_project},
    )


@router.post("/fabrics/{fabric_id}/link-ontology", response_model=APIResponse)
async def link_fabric_ontology(fabric_id: str, body: LinkOntologyRequest):
    if not fabric_store.get(fabric_id):
        raise HTTPException(status_code=404, detail="Fabric not found")
    fabric_store.link_ontology(fabric_id, body.project_id, body.approved_version_id)
    return APIResponse(success=True, message="Fabric linked to ontology project", data=body.model_dump())
