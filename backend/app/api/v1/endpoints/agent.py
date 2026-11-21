"""Agent session memory, episodic log, and fabric feedback loop."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.knowledge import APIResponse
from app.services import agent_memory_service
from app.services.platform.fabric_store import fabric_store

router = APIRouter()


class CreateSessionRequest(BaseModel):
    fabric_id: str
    title: Optional[str] = None


class FeedbackRequest(BaseModel):
    fabric_id: str
    episode_id: Optional[str] = None
    session_id: Optional[str] = None
    rating: str = Field(..., description="up or down")
    outcome: Optional[str] = None
    correction_text: Optional[str] = None
    scope: Optional[str] = Field(
        default=None,
        description="Optional destination: memory, ontology_alias, ontology_constraint, session, discard",
    )


def _require_fabric(fabric_id: str) -> None:
    fabric_store.initialize()
    if not fabric_store.get(fabric_id):
        raise HTTPException(status_code=404, detail="Knowledge fabric not found")


@router.post("/sessions", response_model=APIResponse)
async def create_agent_session(body: CreateSessionRequest):
    _require_fabric(body.fabric_id)
    data = agent_memory_service.create_session(body.fabric_id, title=body.title)
    return APIResponse(success=True, message="Agent session created", data=data)


@router.get("/sessions/{session_id}", response_model=APIResponse)
async def get_agent_session(session_id: str, limit: int = 8):
    found = agent_memory_service.get_session(session_id)
    if not found:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    found["turns"] = agent_memory_service.list_turns(session_id, limit=limit)
    return APIResponse(success=True, message="Agent session retrieved", data=found)


@router.post("/feedback", response_model=APIResponse)
async def submit_agent_feedback(body: FeedbackRequest):
    _require_fabric(body.fabric_id)
    try:
        data = agent_memory_service.submit_feedback(
            fabric_id=body.fabric_id,
            rating=body.rating,
            episode_id=body.episode_id,
            session_id=body.session_id,
            outcome=body.outcome,
            correction_text=body.correction_text,
            scope=body.scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return APIResponse(success=True, message="Feedback captured", data=data)


@router.get("/fabrics/{fabric_id}/enrichment", response_model=APIResponse)
async def list_enrichment(fabric_id: str, status: Optional[str] = None):
    _require_fabric(fabric_id)
    rows = agent_memory_service.list_candidates(fabric_id, status=status)
    return APIResponse(success=True, message="Enrichment queue", data={"candidates": rows})


@router.post("/enrichment/{candidate_id}/approve", response_model=APIResponse)
async def approve_enrichment(candidate_id: str):
    try:
        data = agent_memory_service.approve_candidate(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return APIResponse(success=True, message="Correction applied", data=data)


@router.post("/fabrics/{fabric_id}/memory/{candidate_id}/retire", response_model=APIResponse)
async def retire_memory(fabric_id: str, candidate_id: str):
    _require_fabric(fabric_id)
    try:
        data = agent_memory_service.retire_memory_fact(fabric_id, candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return APIResponse(success=True, message="Memory override retired", data=data)


@router.post("/enrichment/{candidate_id}/reject", response_model=APIResponse)
async def reject_enrichment(candidate_id: str):
    try:
        data = agent_memory_service.reject_candidate(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return APIResponse(success=True, message="Correction rejected", data=data)


@router.get("/fabrics/{fabric_id}/context", response_model=APIResponse)
async def fabric_context_studio(fabric_id: str, limit: int = 30):
    """Episodes, correction queue, memory overrides, and coverage gaps for Context Analysis."""
    _require_fabric(fabric_id)
    from app.services.context.studio import build_studio

    return APIResponse(
        success=True,
        message="Context studio",
        data=build_studio(fabric_id, limit=limit),
    )


@router.post("/fabrics/{fabric_id}/memory/{candidate_id}/promote", response_model=APIResponse)
async def promote_memory(fabric_id: str, candidate_id: str):
    _require_fabric(fabric_id)
    try:
        data = agent_memory_service.promote_memory_fact(fabric_id, candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return APIResponse(success=True, message="Override proposed to the ontology draft", data=data)


@router.get("/fabrics/{fabric_id}/impact", response_model=APIResponse)
async def fabric_impact(fabric_id: str):
    _require_fabric(fabric_id)
    return APIResponse(
        success=True,
        message="Fabric impact summary",
        data=agent_memory_service.impact_summary(fabric_id),
    )
