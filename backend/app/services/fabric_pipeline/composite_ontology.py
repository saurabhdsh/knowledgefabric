"""Shared ontology project selection for composite fabrics (Phase 3)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


def collect_source_ontology_refs(sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarise ontology projects / approved versions on the source fabrics."""
    projects: List[str] = []
    approved: List[Dict[str, str]] = []
    for source in sources:
        pid = source.get("ontology_project_id")
        if pid and pid not in projects:
            projects.append(str(pid))
        vid = source.get("approved_ontology_version_id")
        if vid:
            approved.append({
                "fabric_id": str(source.get("id") or ""),
                "fabric_name": str(source.get("name") or ""),
                "project_id": str(pid or ""),
                "version_id": str(vid),
            })
    return {
        "source_project_ids": projects,
        "approved_versions": approved,
        "shared_project_id": projects[0] if len(projects) == 1 else None,
    }


def choose_shared_ontology_project(
    composite: Dict[str, Any],
    sources: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Pick one ontology project for the composite.

    Preference:
    1. Existing ``composite.ontology_project_id`` (refresh)
    2. Single shared project across all sources that have one
    3. Project of the first source that has an approved version
    4. New ``proj_{composite_suffix}``
    """
    refs = collect_source_ontology_refs(sources)
    existing = composite.get("ontology_project_id")
    if existing:
        project_id = str(existing)
        strategy = "preserve_composite"
    elif refs.get("shared_project_id"):
        project_id = str(refs["shared_project_id"])
        strategy = "reuse_shared_source_project"
    else:
        approved = refs.get("approved_versions") or []
        if approved and approved[0].get("project_id"):
            project_id = str(approved[0]["project_id"])
            strategy = "reuse_approved_source_project"
        else:
            cid = str(composite.get("id") or "composite")
            project_id = f"proj_{cid[-12:]}"
            strategy = "new_composite_project"

    return {
        "project_id": project_id,
        "strategy": strategy,
        "source_project_ids": refs["source_project_ids"],
        "imported_versions": refs["approved_versions"],
        "project_name": f"Shared ontology for {composite.get('name') or composite.get('id')}",
    }
