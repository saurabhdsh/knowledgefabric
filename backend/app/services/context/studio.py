"""Context Analysis payload: episodes, queue, overrides, and coverage gaps."""
from __future__ import annotations

import re
from typing import Any, Dict, List

from app.db.models import RetrievalEpisodeRecord
from app.db.session import db_session, init_db
from app.services import agent_memory_service
from app.services.platform.fabric_store import fabric_store

_SPACE = re.compile(r"\s+")
_PUNCT = re.compile(r"[^a-z0-9\s]")


def _question_key(query: str) -> str:
    text = _PUNCT.sub(" ", (query or "").lower())
    return _SPACE.sub(" ", text).strip()


def coverage_from_episodes(episodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Questions whose envelope had no ontology name, or a name and no evidence."""
    groups: Dict[str, Dict[str, Any]] = {}
    for episode in episodes:
        key = _question_key(str(episode.get("query") or ""))
        if not key:
            continue
        lines = ((episode.get("context_envelope") or {}).get("lines") or [])
        kinds = {str(line.get("kind") or "") for line in lines if isinstance(line, dict)}
        has_ontology = "ontology" in kinds
        has_evidence = bool(kinds & {"table", "passage", "graph"})
        bucket = groups.setdefault(
            key,
            {
                "query": episode.get("query"),
                "count": 0,
                "has_ontology": has_ontology,
                "has_evidence": has_evidence,
                "route": (episode.get("context_envelope") or {}).get("route") or episode.get("route"),
                "confidence": episode.get("confidence"),
            },
        )
        bucket["count"] += 1
        bucket["has_ontology"] = has_ontology
        bucket["has_evidence"] = has_evidence
        bucket["query"] = episode.get("query")
        bucket["route"] = (episode.get("context_envelope") or {}).get("route") or episode.get("route")
        bucket["confidence"] = episode.get("confidence")
    gaps = []
    for bucket in groups.values():
        if bucket["has_ontology"] and bucket["has_evidence"]:
            continue
        gap = "no_ontology" if not bucket["has_ontology"] else "no_evidence"
        gaps.append({**bucket, "gap": gap})
    gaps.sort(key=lambda item: (-int(item["count"]), str(item["query"] or "")))
    return gaps


def _episode_dict(row: RetrievalEpisodeRecord) -> Dict[str, Any]:
    envelope = row.context_envelope if isinstance(row.context_envelope, dict) else None
    return {
        "id": row.id,
        "session_id": row.session_id,
        "query": row.query,
        "answer": row.answer,
        "route": row.route,
        "ontology_version_id": row.ontology_version_id,
        "confidence": row.confidence,
        "context_envelope": envelope,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def build_studio(fabric_id: str, limit: int = 30) -> Dict[str, Any]:
    init_db()
    fabric = fabric_store.get(fabric_id) or {"id": fabric_id}
    with db_session() as session:
        rows = (
            session.query(RetrievalEpisodeRecord)
            .filter(RetrievalEpisodeRecord.fabric_id == fabric_id)
            .order_by(RetrievalEpisodeRecord.created_at.desc())
            .limit(max(1, min(int(limit), 80)))
            .all()
        )
        episodes = [_episode_dict(row) for row in rows]
    queue = agent_memory_service.list_candidates(fabric_id, status="queued")
    overrides = agent_memory_service.approved_facts(fabric_id)
    gaps = coverage_from_episodes(list(reversed(episodes)))
    return {
        "fabric_id": fabric_id,
        "fabric_name": fabric.get("name") or fabric_id,
        "ontology_project_id": fabric.get("ontology_project_id"),
        "approved_ontology_version_id": fabric.get("approved_ontology_version_id"),
        "episodes": episodes,
        "queue": queue,
        "overrides": overrides,
        "coverage": gaps,
        "counts": {
            "episodes": len(episodes),
            "queued": len(queue),
            "overrides": len(overrides),
            "gaps": len(gaps),
        },
    }
