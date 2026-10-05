"""Session memory, episodic query log, and closed-loop fabric corrections."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.db.models import (
    AgentSessionRecord,
    AgentSessionTurnRecord,
    EnrichmentCandidateRecord,
    FabricFeedbackRecord,
    RetrievalEpisodeRecord,
)
from app.db.session import db_session, init_db
from app.services.platform.fabric_store import fabric_store


def _index_memory_fact(documents: List[Dict[str, Any]], fabric_id: str) -> List[str]:
    from app.services.vector_service import vector_service

    return vector_service.add_documents(documents, fabric_id)


def _ensure() -> None:
    init_db()


def create_session(fabric_id: str, *, owner_id: Optional[str] = None, title: Optional[str] = None) -> Dict[str, Any]:
    _ensure()
    expires = datetime.utcnow() + timedelta(hours=max(1, settings.AGENT_SESSION_TTL_HOURS))
    with db_session() as session:
        rec = AgentSessionRecord(
            fabric_id=fabric_id,
            owner_id=owner_id,
            title=(title or "")[:256] or None,
            expires_at=expires,
            turn_count=0,
        )
        session.add(rec)
        session.flush()
        return _session_dict(rec)


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    _ensure()
    with db_session() as session:
        rec = session.get(AgentSessionRecord, session_id)
        if not rec:
            return None
        if rec.expires_at and rec.expires_at < datetime.utcnow():
            return None
        return _session_dict(rec)


def list_turns(session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    _ensure()
    cap = limit if limit is not None else settings.AGENT_SESSION_CONTEXT_TURNS
    cap = max(1, int(cap))
    with db_session() as session:
        rows = (
            session.query(AgentSessionTurnRecord)
            .filter(AgentSessionTurnRecord.session_id == session_id)
            .order_by(AgentSessionTurnRecord.created_at.desc())
            .limit(cap)
            .all()
        )
        rows = list(reversed(rows))
        return [
            {
                "id": row.id,
                "role": row.role,
                "content": row.content,
                "episode_id": row.episode_id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]


def build_query_context(fabric_id: str, session_id: Optional[str]) -> str:
    """Short-term turns plus approved memory facts for the next answer."""
    parts: List[str] = []
    facts = approved_facts(fabric_id)
    if facts:
        lines = ["APPROVED FABRIC MEMORY (these corrections override earlier answers):"]
        for fact in facts[-12:]:
            lines.append(f"- {fact.get('fact')}")
        parts.append("\n".join(lines))
    if session_id:
        turns = list_turns(session_id, settings.AGENT_SESSION_CONTEXT_TURNS)
        if turns:
            lines = ["RECENT CONVERSATION (short-term session memory):"]
            for turn in turns:
                role = "User" if turn["role"] == "user" else "Assistant"
                text = str(turn["content"] or "")
                if len(text) > 1200:
                    text = text[:1200] + "…"
                lines.append(f"{role}: {text}")
            parts.append("\n".join(lines))
    return "\n\n".join(parts)


def record_exchange(
    *,
    fabric_id: str,
    query: str,
    answer: str,
    session_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    llm_provider: Optional[str] = None,
    analytics_intent: Optional[str] = None,
    relevant_chunks: int = 0,
    processing_time: Optional[str] = None,
) -> Dict[str, Any]:
    """Append user + assistant turns and an episodic log row."""
    _ensure()
    with db_session() as session:
        sess = session.get(AgentSessionRecord, session_id) if session_id else None
        if sess is None or (sess.expires_at and sess.expires_at < datetime.utcnow()):
            sess = AgentSessionRecord(
                fabric_id=fabric_id,
                owner_id=owner_id,
                expires_at=datetime.utcnow() + timedelta(hours=max(1, settings.AGENT_SESSION_TTL_HOURS)),
                turn_count=0,
            )
            session.add(sess)
            session.flush()
        elif sess.fabric_id != fabric_id:
            sess = AgentSessionRecord(
                fabric_id=fabric_id,
                owner_id=owner_id,
                expires_at=datetime.utcnow() + timedelta(hours=max(1, settings.AGENT_SESSION_TTL_HOURS)),
                turn_count=0,
            )
            session.add(sess)
            session.flush()

        if int(sess.turn_count or 0) >= max(2, settings.AGENT_SESSION_MAX_TURNS):
            sess = AgentSessionRecord(
                fabric_id=fabric_id,
                owner_id=owner_id,
                expires_at=datetime.utcnow() + timedelta(hours=max(1, settings.AGENT_SESSION_TTL_HOURS)),
                turn_count=0,
            )
            session.add(sess)
            session.flush()

        episode = RetrievalEpisodeRecord(
            fabric_id=fabric_id,
            session_id=sess.id,
            query=query,
            answer=answer,
            llm_provider=llm_provider,
            analytics_intent=analytics_intent,
            relevant_chunks=int(relevant_chunks or 0),
            processing_time=processing_time,
        )
        session.add(episode)
        session.flush()
        session.add(AgentSessionTurnRecord(session_id=sess.id, role="user", content=query, episode_id=episode.id))
        session.add(
            AgentSessionTurnRecord(session_id=sess.id, role="assistant", content=answer, episode_id=episode.id)
        )
        sess.turn_count = int(sess.turn_count or 0) + 2
        sess.updated_at = datetime.utcnow()
        sess.expires_at = datetime.utcnow() + timedelta(hours=max(1, settings.AGENT_SESSION_TTL_HOURS))
        return {"session_id": sess.id, "episode_id": episode.id}


def submit_feedback(
    *,
    fabric_id: str,
    rating: str,
    episode_id: Optional[str] = None,
    session_id: Optional[str] = None,
    outcome: Optional[str] = None,
    correction_text: Optional[str] = None,
) -> Dict[str, Any]:
    _ensure()
    rating_n = str(rating or "").strip().lower()
    if rating_n not in {"up", "down"}:
        raise ValueError("rating must be 'up' or 'down'")
    outcome_n = str(outcome or "").strip().lower() or None
    allowed_outcomes = {None, "helpful", "resolved", "incorrect", "escalated"}
    if outcome_n not in allowed_outcomes:
        outcome_n = None
    correction = (correction_text or "").strip() or None

    with db_session() as session:
        episode = session.get(RetrievalEpisodeRecord, episode_id) if episode_id else None
        feedback = FabricFeedbackRecord(
            fabric_id=fabric_id,
            episode_id=episode_id,
            session_id=session_id or (episode.session_id if episode else None),
            rating=rating_n,
            outcome=outcome_n,
            correction_text=correction,
            status="captured",
        )
        session.add(feedback)
        session.flush()
        if episode:
            episode.feedback_flag = rating_n
        candidate_id = None
        needs_queue = rating_n == "down" or bool(correction) or outcome_n == "incorrect"
        if needs_queue:
            proposed = correction or (
                f"The previous answer was marked {outcome_n or 'incorrect'} "
                f"for the question: {(episode.query if episode else '')[:500]}"
            )
            candidate = EnrichmentCandidateRecord(
                fabric_id=fabric_id,
                feedback_id=feedback.id,
                episode_id=episode_id,
                query=(episode.query if episode else "")[:4000],
                proposed_fact=proposed,
                status="queued",
            )
            session.add(candidate)
            session.flush()
            feedback.status = "queued"
            candidate_id = candidate.id
        return {
            "feedback_id": feedback.id,
            "status": feedback.status,
            "enrichment_candidate_id": candidate_id,
        }


def list_candidates(fabric_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    _ensure()
    with db_session() as session:
        query = session.query(EnrichmentCandidateRecord).filter(EnrichmentCandidateRecord.fabric_id == fabric_id)
        if status:
            query = query.filter(EnrichmentCandidateRecord.status == status)
        rows = query.order_by(EnrichmentCandidateRecord.created_at.desc()).limit(50).all()
        return [_candidate_dict(row) for row in rows]


def approve_candidate(candidate_id: str) -> Dict[str, Any]:
    """Write an approved correction into the fabric index and metadata."""
    _ensure()
    with db_session() as session:
        candidate = session.get(EnrichmentCandidateRecord, candidate_id)
        if not candidate:
            raise ValueError("Enrichment candidate not found")
        if candidate.status == "applied":
            return _candidate_dict(candidate)
        fact_text = (
            f"APPROVED FABRIC CORRECTION | question: {candidate.query} | "
            f"fact: {candidate.proposed_fact}"
        )
        chunk_ids = _index_memory_fact(
            [
                {
                    "content": fact_text,
                    "source_name": "episodic_memory",
                    "file_name": "fabric_memory",
                    "page_number": 0,
                    "created_at": datetime.utcnow().isoformat(),
                    "metadata": {
                        "chunk_type": "memory_fact",
                        "source_type": "episodic_memory",
                        "candidate_id": candidate.id,
                    },
                }
            ],
            candidate.fabric_id,
        )
        candidate.status = "applied"
        candidate.applied_at = datetime.utcnow()
        candidate.vector_chunk_id = chunk_ids[0] if chunk_ids else None
        if candidate.feedback_id:
            feedback = session.get(FabricFeedbackRecord, candidate.feedback_id)
            if feedback:
                feedback.status = "applied"
        fabric_id = candidate.fabric_id
        fact_payload = {
            "candidate_id": candidate.id,
            "fact": candidate.proposed_fact,
            "query": candidate.query,
            "applied_at": candidate.applied_at.isoformat(),
            "vector_chunk_id": candidate.vector_chunk_id,
        }
        result = _candidate_dict(candidate)

    fabric = fabric_store.get(fabric_id) or {"id": fabric_id, "name": fabric_id}
    facts = list(fabric.get("memory_facts") or [])
    facts.append(fact_payload)
    fabric["memory_facts"] = facts[-100:]
    fabric["memory_fact_count"] = len(fabric["memory_facts"])
    fabric["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    try:
        fabric["total_chunks"] = int(fabric.get("total_chunks") or 0) + 1
    except (TypeError, ValueError):
        fabric["total_chunks"] = 1
    fabric_store.save(fabric)
    result["fabric_memory_fact_count"] = fabric["memory_fact_count"]
    return result


def reject_candidate(candidate_id: str) -> Dict[str, Any]:
    _ensure()
    with db_session() as session:
        candidate = session.get(EnrichmentCandidateRecord, candidate_id)
        if not candidate:
            raise ValueError("Enrichment candidate not found")
        candidate.status = "rejected"
        if candidate.feedback_id:
            feedback = session.get(FabricFeedbackRecord, candidate.feedback_id)
            if feedback and feedback.status == "queued":
                feedback.status = "rejected"
        return _candidate_dict(candidate)


def approved_facts(fabric_id: str) -> List[Dict[str, Any]]:
    fabric = fabric_store.get(fabric_id) or {}
    facts = fabric.get("memory_facts") or []
    return [f for f in facts if isinstance(f, dict)]


def impact_summary(fabric_id: str) -> Dict[str, Any]:
    _ensure()
    since = datetime.utcnow() - timedelta(days=30)
    with db_session() as session:
        episodes = (
            session.query(RetrievalEpisodeRecord)
            .filter(RetrievalEpisodeRecord.fabric_id == fabric_id, RetrievalEpisodeRecord.created_at >= since)
            .all()
        )
        feedback_rows = (
            session.query(FabricFeedbackRecord)
            .filter(FabricFeedbackRecord.fabric_id == fabric_id, FabricFeedbackRecord.created_at >= since)
            .all()
        )
        applied = (
            session.query(EnrichmentCandidateRecord)
            .filter(
                EnrichmentCandidateRecord.fabric_id == fabric_id,
                EnrichmentCandidateRecord.status == "applied",
            )
            .count()
        )
        queued = (
            session.query(EnrichmentCandidateRecord)
            .filter(
                EnrichmentCandidateRecord.fabric_id == fabric_id,
                EnrichmentCandidateRecord.status == "queued",
            )
            .count()
        )
    total = len(episodes)
    rated = len(feedback_rows)
    helpful = sum(1 for row in feedback_rows if row.rating == "up")
    return {
        "fabric_id": fabric_id,
        "window_days": 30,
        "queries": total,
        "feedback_count": rated,
        "feedback_rate": round(rated / total, 3) if total else 0.0,
        "helpful_count": helpful,
        "queued_corrections": queued,
        "applied_corrections": applied,
        "approved_memory_facts": len(approved_facts(fabric_id)),
    }


def _session_dict(rec: AgentSessionRecord) -> Dict[str, Any]:
    return {
        "session_id": rec.id,
        "fabric_id": rec.fabric_id,
        "title": rec.title,
        "turn_count": rec.turn_count,
        "expires_at": rec.expires_at.isoformat() if rec.expires_at else None,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
    }


def _candidate_dict(row: EnrichmentCandidateRecord) -> Dict[str, Any]:
    return {
        "id": row.id,
        "fabric_id": row.fabric_id,
        "feedback_id": row.feedback_id,
        "episode_id": row.episode_id,
        "query": row.query,
        "proposed_fact": row.proposed_fact,
        "status": row.status,
        "vector_chunk_id": row.vector_chunk_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "applied_at": row.applied_at.isoformat() if row.applied_at else None,
    }
