"""Review and governance routes for one fabric.

Mounted under ``/knowledge`` ahead of the main fabric router. Everything here
reads or changes what a fabric is allowed to state or who is allowed to use
it, so each route checks the caller's role on that fabric first.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from app.core.user_context import get_current_user_id
from app.models.knowledge import APIResponse
from app.services.enterprise.ops import AccessDenied, authorize, record_audit
from app.services.platform.fabric_store import fabric_store

router = APIRouter()


def _fabric_or_404(fabric_id: str, action: str) -> Dict[str, Any]:
    fabric = fabric_store.get(fabric_id)
    if not fabric:
        raise HTTPException(status_code=404, detail="Knowledge fabric not found")
    try:
        authorize(fabric, action)
    except AccessDenied as denied:
        raise HTTPException(status_code=403, detail=denied.reason) from denied
    return fabric


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Relationships between tables: accepted, two-column, and waiting for review
# --------------------------------------------------------------------------

@router.get("/{fabric_id}/relationships", response_model=APIResponse)
async def get_fabric_relationships(fabric_id: str):
    """Measured links between tables, with the evidence behind each one.

    ``accepted`` and ``two_column`` are used for joins, the graph, and the
    ontology. ``needs_review`` are plausible links the data does not prove;
    they are not used until someone accepts them.
    """
    _fabric_or_404(fabric_id, "query")
    from app.services.fabric_pipeline.runner import load_profile

    profile = load_profile(fabric_id) or {}
    candidates = list(profile.get("foreign_key_candidates") or [])
    return APIResponse(
        success=True,
        message="OK",
        data={
            "fabric_id": fabric_id,
            "accepted": list(profile.get("foreign_keys") or []),
            "two_column": list(profile.get("composite_foreign_keys") or []),
            "needs_review": [c for c in candidates if c.get("status") == "needs_review"],
            "rejected": [c for c in candidates if c.get("status") == "rejected"],
            "acceptance_threshold": _threshold(),
        },
    )


def _threshold() -> float:
    from app.core.config import settings

    return float(settings.FABRIC_FK_MIN_OVERLAP)


@router.post("/{fabric_id}/relationships/review", response_model=APIResponse)
async def review_fabric_relationship(fabric_id: str, request: dict):
    """Accept or reject a link that is waiting for review.

    Body: ``from_table``, ``from_column`` (or ``from_columns``), ``to_table``,
    ``to_column`` (or ``to_columns``), ``decision`` = ``accept`` | ``reject``.
    The decision is stored on the fabric and applied again on every rebuild.
    """
    fabric = _fabric_or_404(fabric_id, "admin")
    from app.services.fabric_pipeline.pipelines import _tabular_record_fields
    from app.services.fabric_pipeline.runner import load_profile, save_profile
    from app.services.fabric_pipeline.tabular_profiler import _link_key, apply_relationship_decisions

    decision = str(request.get("decision") or "").strip().lower()
    if decision not in ("accept", "reject"):
        raise HTTPException(status_code=400, detail="decision must be accept or reject")
    link = {
        "from_table": request.get("from_table"),
        "from_columns": request.get("from_columns") or [request.get("from_column")],
        "to_table": request.get("to_table"),
        "to_columns": request.get("to_columns") or [request.get("to_column")],
    }
    key = _link_key(link)
    if not key[0] or not key[1] or not key[2] or not key[3]:
        raise HTTPException(status_code=400, detail="from_table, from_column, to_table and to_column are required")

    profile = load_profile(fabric_id)
    if not profile:
        raise HTTPException(status_code=409, detail="This fabric has no table profile to review")
    pending = [
        c for c in profile.get("foreign_key_candidates") or []
        if c.get("status") == "needs_review" and _link_key(c) == key
    ]
    if not pending:
        raise HTTPException(status_code=404, detail="That link is not waiting for review")

    entry = {**link, "decision": decision, "by": get_current_user_id() or "system", "at": _now()}
    apply_relationship_decisions(profile, [entry])
    save_profile(fabric_id, profile)

    decisions: List[Dict[str, Any]] = [
        d for d in (fabric.get("relationship_decisions") or []) if _link_key(d) != key
    ]
    decisions.append(entry)
    fabric["relationship_decisions"] = decisions
    conn = dict(fabric.get("connection_info") or {})
    refreshed = _tabular_record_fields(profile, {})
    for field in ("tables", "schema_tables", "relationships", "composite_relationships", "relationship_candidates"):
        conn[field] = refreshed[field]
    fabric["connection_info"] = conn
    fabric_store.save(fabric)
    record_audit(
        fabric_id,
        f"relationship_{decision}",
        detail={
            "from": f"{key[0]}.({', '.join(key[1])})",
            "to": f"{key[2]}.({', '.join(key[3])})",
            "overlap": pending[0].get("overlap"),
        },
    )
    return APIResponse(
        success=True,
        message="Link accepted. It is now used for joins and the graph." if decision == "accept"
        else "Link rejected. It will not be listed again.",
        data={
            "decision": entry,
            "accepted_count": len(profile.get("foreign_keys") or []),
            "needs_review_count": (profile.get("summary") or {}).get("foreign_key_review_count", 0),
            "ontology_note": (
                "Run ontology discovery again to add this link to a new draft. "
                "The approved ontology is unchanged."
            ) if decision == "accept" else None,
        },
    )
