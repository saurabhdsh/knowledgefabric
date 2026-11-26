"""Designed Context Layer profiles — sit between Fabric and Agents.

A profile attaches one or more fabrics, an optional ontology lens, scope,
business rules, decision playbook, evidence policy, and steward memory notes.
Agents pin a ``context_id`` so they operate inside that contract, not on raw fabric alone.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import settings

_STORE = os.path.join(settings.DATA_DIR, "context_profiles.json")
_SLUG = re.compile(r"[^a-z0-9]+")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> Dict[str, Any]:
    os.makedirs(os.path.dirname(_STORE) or ".", exist_ok=True)
    if not os.path.isfile(_STORE):
        return {"profiles": []}
    try:
        with open(_STORE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("profiles"), list):
            return data
    except Exception:
        pass
    return {"profiles": []}


def _save(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(_STORE) or ".", exist_ok=True)
    tmp = f"{_STORE}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, _STORE)


def _slugify(name: str) -> str:
    base = _SLUG.sub("-", (name or "context").strip().lower()).strip("-") or "context"
    return base[:48]


def default_decision_schema() -> Dict[str, Any]:
    return {
        "keys": ["decision", "confidence_0_1", "evidence_fields", "reasoning_one_line"],
        "decisions": ["pay", "deny", "hold", "human_review"],
        "human_review_if_confidence_below": 0.7,
        "require_evidence": True,
    }


def empty_profile(
    *,
    name: str,
    fabric_id: str,
    fabric_name: str = "",
    purpose: str = "",
) -> Dict[str, Any]:
    pid = f"ctx_{_slugify(name)}_{uuid.uuid4().hex[:8]}"
    return {
        "id": pid,
        "name": name.strip() or "Untitled context",
        "status": "draft",  # draft | published
        "version": 1,
        "purpose": purpose.strip()
        or "Operating contract between the knowledge fabric and agents.",
        "fabric_ids": [fabric_id] if fabric_id else [],
        "primary_fabric_id": fabric_id or None,
        "fabric_name": fabric_name or "",
        "ontology_project_id": None,
        "ontology_version_id": None,
        "scope": {
            "collections": [],  # empty = all collections on fabric
            "entity_types": [],
            "exclude_collections": [],
        },
        "rules": [],  # [{id, text, severity}]
        "playbook": {
            "routes": ["pay", "deny", "hold", "human_review"],
            "default_route": "human_review",
            "notes": "",
        },
        "evidence_policy": {
            "require_table_or_passage": True,
            "prefer_kinds": ["table", "passage", "graph", "ontology"],
            "fail_closed": True,
        },
        "decision_schema": default_decision_schema(),
        "memory_notes": [],  # steward typed notes beyond source rows
        "agent_bindings": [],  # [{agent_key, label, bound_at}]
        "created_at": _now(),
        "updated_at": _now(),
        "published_at": None,
    }


def list_profiles(fabric_id: Optional[str] = None) -> List[Dict[str, Any]]:
    rows = list(_load().get("profiles") or [])
    if fabric_id:
        rows = [
            p
            for p in rows
            if fabric_id == p.get("primary_fabric_id")
            or fabric_id in (p.get("fabric_ids") or [])
        ]
    rows.sort(key=lambda p: str(p.get("updated_at") or ""), reverse=True)
    return rows


def get_profile(context_id: str) -> Optional[Dict[str, Any]]:
    for row in _load().get("profiles") or []:
        if row.get("id") == context_id:
            return row
    return None


def create_profile(payload: Dict[str, Any]) -> Dict[str, Any]:
    name = str(payload.get("name") or "Untitled context")
    fabric_id = str(payload.get("fabric_id") or payload.get("primary_fabric_id") or "")
    if not fabric_id:
        raise ValueError("fabric_id is required to attach a knowledge fabric")
    profile = empty_profile(
        name=name,
        fabric_id=fabric_id,
        fabric_name=str(payload.get("fabric_name") or ""),
        purpose=str(payload.get("purpose") or ""),
    )
    for key in (
        "ontology_project_id",
        "ontology_version_id",
        "scope",
        "rules",
        "playbook",
        "evidence_policy",
        "decision_schema",
        "memory_notes",
    ):
        if key in payload and payload[key] is not None:
            profile[key] = payload[key]
    data = _load()
    data.setdefault("profiles", []).append(profile)
    _save(data)
    return profile


def update_profile(context_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    data = _load()
    profiles = data.get("profiles") or []
    idx = next((i for i, p in enumerate(profiles) if p.get("id") == context_id), None)
    if idx is None:
        raise ValueError("Context profile not found")
    row = dict(profiles[idx])
    allowed = {
        "name",
        "purpose",
        "fabric_ids",
        "primary_fabric_id",
        "fabric_name",
        "ontology_project_id",
        "ontology_version_id",
        "scope",
        "rules",
        "playbook",
        "evidence_policy",
        "decision_schema",
        "memory_notes",
        "agent_bindings",
        "status",
    }
    for key, value in patch.items():
        if key in allowed:
            row[key] = value
    if patch.get("fabric_id"):
        fid = str(patch["fabric_id"])
        row["primary_fabric_id"] = fid
        ids = list(row.get("fabric_ids") or [])
        if fid not in ids:
            ids.insert(0, fid)
        row["fabric_ids"] = ids
    row["updated_at"] = _now()
    profiles[idx] = row
    data["profiles"] = profiles
    _save(data)
    return row


def publish_profile(context_id: str) -> Dict[str, Any]:
    data = _load()
    profiles = data.get("profiles") or []
    idx = next((i for i, p in enumerate(profiles) if p.get("id") == context_id), None)
    if idx is None:
        raise ValueError("Context profile not found")
    row = dict(profiles[idx])
    version = int(row.get("version") or 1)
    if row.get("status") == "published":
        version += 1
    row["status"] = "published"
    row["version"] = version
    row["published_at"] = _now()
    row["updated_at"] = _now()
    profiles[idx] = row
    data["profiles"] = profiles
    _save(data)
    return row


def delete_profile(context_id: str) -> None:
    data = _load()
    before = len(data.get("profiles") or [])
    data["profiles"] = [p for p in (data.get("profiles") or []) if p.get("id") != context_id]
    if len(data["profiles"]) == before:
        raise ValueError("Context profile not found")
    _save(data)


def bind_agent(context_id: str, agent_key: str, label: str = "") -> Dict[str, Any]:
    row = get_profile(context_id)
    if not row:
        raise ValueError("Context profile not found")
    bindings = list(row.get("agent_bindings") or [])
    bindings = [b for b in bindings if b.get("agent_key") != agent_key]
    bindings.append(
        {
            "agent_key": agent_key,
            "label": label or agent_key,
            "bound_at": _now(),
        }
    )
    return update_profile(context_id, {"agent_bindings": bindings})


def unbind_agent(context_id: str, agent_key: str) -> Dict[str, Any]:
    row = get_profile(context_id)
    if not row:
        raise ValueError("Context profile not found")
    bindings = [b for b in (row.get("agent_bindings") or []) if b.get("agent_key") != agent_key]
    return update_profile(context_id, {"agent_bindings": bindings})


def render_agent_preamble(profile: Dict[str, Any]) -> str:
    """Text injected ahead of fabric retrieval so agents honor the designed layer."""
    lines: List[str] = [
        "DESIGNED CONTEXT LAYER (operating contract — obey before answering):",
        f"Context: {profile.get('name')} ({profile.get('id')}) · status={profile.get('status')} · v{profile.get('version')}",
        f"Purpose: {profile.get('purpose') or '—'}",
        f"Primary fabric: {profile.get('primary_fabric_id') or '—'}",
    ]
    if profile.get("ontology_version_id"):
        lines.append(f"Ontology lens: {profile['ontology_version_id']}")
    scope = profile.get("scope") or {}
    cols = scope.get("collections") or []
    if cols:
        lines.append("Scope collections: " + ", ".join(str(c) for c in cols))
    excl = scope.get("exclude_collections") or []
    if excl:
        lines.append("Exclude collections: " + ", ".join(str(c) for c in excl))
    rules = profile.get("rules") or []
    if rules:
        lines.append("Business rules:")
        for rule in rules[:20]:
            if isinstance(rule, dict):
                lines.append(f"- [{rule.get('severity') or 'info'}] {rule.get('text') or ''}")
            else:
                lines.append(f"- {rule}")
    playbook = profile.get("playbook") or {}
    routes = playbook.get("routes") or []
    if routes:
        lines.append(
            "Decision playbook routes: "
            + ", ".join(str(r) for r in routes)
            + f" · default={playbook.get('default_route') or 'human_review'}"
        )
    if playbook.get("notes"):
        lines.append(f"Playbook notes: {playbook['notes']}")
    schema = profile.get("decision_schema") or {}
    if schema:
        lines.append(
            "Return structured decisions when deciding. Keys: "
            + ", ".join(str(k) for k in (schema.get("keys") or []))
        )
        thr = schema.get("human_review_if_confidence_below")
        if thr is not None:
            lines.append(f"If confidence < {thr}, decision must be human_review.")
        if schema.get("require_evidence"):
            lines.append("Every decision must cite evidence_fields from the fabric envelope.")
    policy = profile.get("evidence_policy") or {}
    if policy.get("fail_closed"):
        lines.append("Fail closed: if no table/passage/graph evidence, do not invent facts — use human_review.")
    notes = profile.get("memory_notes") or []
    if notes:
        lines.append("Steward context (beyond source rows):")
        for note in notes[:15]:
            if isinstance(note, dict):
                lines.append(f"- {note.get('text') or ''}")
            else:
                lines.append(f"- {note}")
    lines.append("End of designed context layer.")
    return "\n".join(lines)


def agent_attach_snippet(profile: Dict[str, Any], *, api_base: str = "https://cuweave.com") -> str:
    fabric_id = profile.get("primary_fabric_id") or ""
    context_id = profile.get("id") or ""
    return (
        f"# Attach Context Layer + Knowledge Fabric to your agent\n"
        f"POST {api_base.rstrip('/')}/api/v1/knowledge/{fabric_id}/query\n"
        "Content-Type: application/json\n\n"
        "{\n"
        f'  "query": "<agent question>",\n'
        f'  "context_id": "{context_id}",\n'
        f'  "session_id": "<optional>"\n'
        "}\n"
    )
