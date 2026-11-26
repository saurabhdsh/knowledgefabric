"""Agent session memory, episodic log, fabric feedback, and Context Layer profiles."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.knowledge import APIResponse
from app.services import agent_memory_service
from app.services.context import profiles as context_profiles
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


class ContextProfileCreate(BaseModel):
    name: str
    fabric_id: str
    fabric_name: Optional[str] = None
    purpose: Optional[str] = None
    ontology_project_id: Optional[str] = None
    ontology_version_id: Optional[str] = None
    scope: Optional[Dict[str, Any]] = None
    rules: Optional[List[Any]] = None
    playbook: Optional[Dict[str, Any]] = None
    evidence_policy: Optional[Dict[str, Any]] = None
    decision_schema: Optional[Dict[str, Any]] = None
    memory_notes: Optional[List[Any]] = None


class ContextProfileUpdate(BaseModel):
    name: Optional[str] = None
    purpose: Optional[str] = None
    fabric_id: Optional[str] = None
    fabric_name: Optional[str] = None
    fabric_ids: Optional[List[str]] = None
    primary_fabric_id: Optional[str] = None
    ontology_project_id: Optional[str] = None
    ontology_version_id: Optional[str] = None
    scope: Optional[Dict[str, Any]] = None
    rules: Optional[List[Any]] = None
    playbook: Optional[Dict[str, Any]] = None
    evidence_policy: Optional[Dict[str, Any]] = None
    decision_schema: Optional[Dict[str, Any]] = None
    memory_notes: Optional[List[Any]] = None
    agent_bindings: Optional[List[Any]] = None
    status: Optional[str] = None


class BindAgentRequest(BaseModel):
    agent_key: str
    label: Optional[str] = None


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

    studio = build_studio(fabric_id, limit=limit)
    studio["profiles"] = context_profiles.list_profiles(fabric_id)
    return APIResponse(
        success=True,
        message="Context studio",
        data=studio,
    )


@router.get("/context-profiles", response_model=APIResponse)
async def list_context_profiles(fabric_id: Optional[str] = None):
    rows = context_profiles.list_profiles(fabric_id)
    return APIResponse(success=True, message="Context profiles", data={"profiles": rows})


@router.post("/context-profiles", response_model=APIResponse)
async def create_context_profile(body: ContextProfileCreate):
    _require_fabric(body.fabric_id)
    try:
        profile = context_profiles.create_profile(body.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return APIResponse(success=True, message="Context profile created", data=profile)


@router.get("/context-profiles/{context_id}", response_model=APIResponse)
async def get_context_profile(context_id: str):
    profile = context_profiles.get_profile(context_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Context profile not found")
    profile = dict(profile)
    profile["agent_snippet"] = context_profiles.agent_attach_snippet(profile)
    profile["preamble_preview"] = context_profiles.render_agent_preamble(profile)
    return APIResponse(success=True, message="Context profile", data=profile)


@router.patch("/context-profiles/{context_id}", response_model=APIResponse)
async def patch_context_profile(context_id: str, body: ContextProfileUpdate):
    patch = body.model_dump(exclude_none=True)
    if patch.get("fabric_id"):
        _require_fabric(str(patch["fabric_id"]))
    try:
        profile = context_profiles.update_profile(context_id, patch)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return APIResponse(success=True, message="Context profile updated", data=profile)


@router.post("/context-profiles/{context_id}/publish", response_model=APIResponse)
async def publish_context_profile(context_id: str):
    try:
        profile = context_profiles.publish_profile(context_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return APIResponse(success=True, message="Context profile published", data=profile)


@router.delete("/context-profiles/{context_id}", response_model=APIResponse)
async def delete_context_profile(context_id: str):
    try:
        context_profiles.delete_profile(context_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return APIResponse(success=True, message="Context profile deleted", data={"id": context_id})


@router.post("/context-profiles/{context_id}/bind-agent", response_model=APIResponse)
async def bind_agent_to_context(context_id: str, body: BindAgentRequest):
    try:
        profile = context_profiles.bind_agent(context_id, body.agent_key, body.label or "")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return APIResponse(success=True, message="Agent bound to context layer", data=profile)


@router.post("/context-profiles/{context_id}/unbind-agent", response_model=APIResponse)
async def unbind_agent_from_context(context_id: str, body: BindAgentRequest):
    try:
        profile = context_profiles.unbind_agent(context_id, body.agent_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return APIResponse(success=True, message="Agent unbound", data=profile)


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
