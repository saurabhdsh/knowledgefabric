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


def _as_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_episode(episode_id: str) -> Optional[Dict[str, Any]]:
    """Return one episodic row, including the context envelope stored with it."""
    _ensure()
    with db_session() as session:
        row = session.get(RetrievalEpisodeRecord, episode_id)
        if not row:
            return None
        return {
            "id": row.id,
            "fabric_id": row.fabric_id,
            "session_id": row.session_id,
            "query": row.query,
            "answer": row.answer,
            "route": row.route,
            "ontology_version_id": row.ontology_version_id,
            "confidence": row.confidence,
            "context_envelope": row.context_envelope,
            "analytics_intent": row.analytics_intent,
            "relevant_chunks": row.relevant_chunks,
        }


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
                if turn["role"] == "note":
                    role = "Note"
                elif turn["role"] == "user":
                    role = "User"
                else:
                    role = "Assistant"
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
    route: Optional[str] = None,
    ontology_version_id: Optional[str] = None,
    confidence: Optional[float] = None,
    context_envelope: Optional[Dict[str, Any]] = None,
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
            route=(route or (context_envelope or {}).get("route") or None),
            ontology_version_id=(
                ontology_version_id
                or (context_envelope or {}).get("ontology_version_id")
                or None
            ),
            confidence=_as_float(confidence if confidence is not None else (context_envelope or {}).get("confidence")),
            context_envelope=context_envelope,
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


def _context_for_classification(fabric_id: str, episode_id: Optional[str]) -> Dict[str, Any]:
    """Classes, attributes, columns, and later episode text used to place a correction."""
    from app.services.context.classifier import classify_correction
    from app.services.fabric_pipeline.runner import load_profile
    from app.services.fabric_pipeline.table_store import table_store
    from app.services.ontology.ontology_db_repository import ontology_db_repository
    from app.services.ontology.ontology_persistence_service import OntologyPersistenceService

    fabric = fabric_store.get(fabric_id) or {}
    classes: List[Dict[str, Any]] = []
    attributes: List[Dict[str, Any]] = []
    version = None
    project_id = fabric.get("ontology_project_id")
    if project_id:
        try:
            for meta in OntologyPersistenceService().list_versions_for_project(project_id):
                found = ontology_db_repository.get_version(meta.get("id"))
                if found and found.is_draft:
                    version = found
                    break
        except Exception:
            version = None
    if version is None and fabric.get("approved_ontology_version_id"):
        try:
            version = ontology_db_repository.get_version(fabric.get("approved_ontology_version_id"))
        except Exception:
            version = None
    if version is not None:
        class_names = {c.id: c.name for c in version.classes}
        classes = [{"name": c.name, "id": c.id} for c in version.classes]
        attributes = [
            {"name": a.attribute_name, "id": a.id, "class_name": class_names.get(a.class_id)}
            for a in version.attributes
        ]
    columns: List[str] = []
    try:
        if table_store.exists(fabric_id):
            profile = load_profile(fabric_id) or {}
            for table in profile.get("tables") or []:
                for column in table.get("columns") or []:
                    if column.get("name"):
                        columns.append(str(column["name"]))
    except Exception:
        columns = []
    later: List[str] = []
    if episode_id:
        with db_session() as session:
            episode = session.get(RetrievalEpisodeRecord, episode_id)
            if episode and episode.created_at:
                rows = (
                    session.query(RetrievalEpisodeRecord)
                    .filter(
                        RetrievalEpisodeRecord.fabric_id == fabric_id,
                        RetrievalEpisodeRecord.created_at > episode.created_at,
                    )
                    .all()
                )
                later = [f"{row.query}\n{row.answer}" for row in rows]
    return {
        "classify": classify_correction,
        "classes": classes,
        "attributes": attributes,
        "columns": columns,
        "later_texts": later,
    }


def _discard_contradicted(session, fabric_id: str, new_text: str) -> None:
    from app.services.context.classifier import contradicts

    rows = (
        session.query(EnrichmentCandidateRecord)
        .filter(
            EnrichmentCandidateRecord.fabric_id == fabric_id,
            EnrichmentCandidateRecord.status == "queued",
        )
        .all()
    )
    for row in rows:
        if contradicts(new_text, row.proposed_fact or ""):
            row.status = "discarded"
            row.destination = "discard"
            row.classification_reason = "A later correction contradicts this one."


def append_session_note(session_id: Optional[str], fabric_id: str, text: str) -> str:
    """Keep a correction on the session until it expires."""
    _ensure()
    with db_session() as session:
        sess = session.get(AgentSessionRecord, session_id) if session_id else None
        if sess is None or (sess.expires_at and sess.expires_at < datetime.utcnow()):
            sess = AgentSessionRecord(
                fabric_id=fabric_id,
                expires_at=datetime.utcnow() + timedelta(hours=max(1, settings.AGENT_SESSION_TTL_HOURS)),
                turn_count=0,
            )
            session.add(sess)
            session.flush()
        session.add(AgentSessionTurnRecord(session_id=sess.id, role="note", content=text[:4000]))
        sess.turn_count = int(sess.turn_count or 0) + 1
        sess.updated_at = datetime.utcnow()
        return sess.id


def submit_feedback(
    *,
    fabric_id: str,
    rating: str,
    episode_id: Optional[str] = None,
    session_id: Optional[str] = None,
    outcome: Optional[str] = None,
    correction_text: Optional[str] = None,
    scope: Optional[str] = None,
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
    proposed_preview = correction or ""
    classification = {
        "destination": "memory",
        "reason": "The correction does not name an ontology alias or rule, so it stays fabric memory.",
        "alias": None,
        "attribute_name": None,
        "related_entity": None,
    }
    if proposed_preview or scope:
        try:
            ctx = _context_for_classification(fabric_id, episode_id)
            classification = ctx["classify"](
                proposed_preview,
                classes=ctx["classes"],
                attributes=ctx["attributes"],
                columns=ctx["columns"],
                later_texts=ctx["later_texts"],
                scope=scope,
            )
        except Exception:
            classification["reason"] = "Classification was unavailable, so the correction stays fabric memory."

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
        destination = classification.get("destination") or "memory"
        needs_queue = rating_n == "down" or bool(correction) or outcome_n == "incorrect"
        if needs_queue and destination == "session":
            note = correction or "Correction limited to this session."
            feedback.status = "noted"
            note_session_id = session_id or (episode.session_id if episode else None)
            sess = session.get(AgentSessionRecord, note_session_id) if note_session_id else None
            if sess is None or (sess.expires_at and sess.expires_at < datetime.utcnow()):
                sess = AgentSessionRecord(
                    fabric_id=fabric_id,
                    expires_at=datetime.utcnow() + timedelta(hours=max(1, settings.AGENT_SESSION_TTL_HOURS)),
                    turn_count=0,
                )
                session.add(sess)
                session.flush()
            session.add(AgentSessionTurnRecord(session_id=sess.id, role="note", content=note[:4000]))
            sess.turn_count = int(sess.turn_count or 0) + 1
            sess.updated_at = datetime.utcnow()
            return {
                "feedback_id": feedback.id,
                "status": "noted",
                "destination": "session",
                "classification_reason": classification.get("reason"),
                "session_id": sess.id,
                "enrichment_candidate_id": None,
            }
        if needs_queue:
            proposed = correction or (
                f"The previous answer was marked {outcome_n or 'incorrect'} "
                f"for the question: {(episode.query if episode else '')[:500]}"
            )
            if destination != "discard":
                _discard_contradicted(session, fabric_id, proposed)
            status = "discarded" if destination == "discard" else "queued"
            candidate = EnrichmentCandidateRecord(
                fabric_id=fabric_id,
                feedback_id=feedback.id,
                episode_id=episode_id,
                query=(episode.query if episode else "")[:4000],
                proposed_fact=proposed,
                status=status,
                destination=destination,
                classification_reason=classification.get("reason"),
                classification=classification,
            )
            session.add(candidate)
            session.flush()
            feedback.status = status
            candidate_id = candidate.id
        return {
            "feedback_id": feedback.id,
            "status": feedback.status,
            "destination": destination if needs_queue else None,
            "classification_reason": classification.get("reason") if needs_queue else None,
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
    """Apply a queued correction to memory or to the ontology draft.

    Memory updates the next answer and is not embedded as source text.
    An alias or a rule is written onto the draft and waits for ontology approval.
    """
    _ensure()
    with db_session() as session:
        candidate = session.get(EnrichmentCandidateRecord, candidate_id)
        if not candidate:
            raise ValueError("Enrichment candidate not found")
        if candidate.status == "applied":
            return _candidate_dict(candidate)
        destination = candidate.destination or "memory"
        if destination == "discard" or candidate.status == "discarded":
            candidate.status = "discarded"
            return _candidate_dict(candidate)
        if destination == "session":
            candidate.status = "noted"
            return _candidate_dict(candidate)
        classification = dict(candidate.classification or {})
        classification.setdefault("destination", destination)
        fabric_id = candidate.fabric_id
        proposed = candidate.proposed_fact
        query = candidate.query
        episode_id = candidate.episode_id
        feedback_id = candidate.feedback_id
        if destination in {"ontology_alias", "ontology_constraint"}:
            from app.services.context.promote import apply_ontology_candidate

            fabric = fabric_store.get(fabric_id) or {"id": fabric_id}
            try:
                applied = apply_ontology_candidate(fabric, classification, proposed, episode_id)
            except ValueError:
                destination = "memory"
                candidate.destination = "memory"
                candidate.classification_reason = (
                    "No ontology draft could take this correction, so it was stored as fabric memory."
                )
                applied = None
            else:
                candidate.status = "applied"
                candidate.applied_at = datetime.utcnow()
                candidate.destination = destination
                if feedback_id:
                    feedback = session.get(FabricFeedbackRecord, feedback_id)
                    if feedback:
                        feedback.status = "applied"
                result = _candidate_dict(candidate)
                result["ontology_version_id"] = applied.get("ontology_version_id")
                result["element_id"] = applied.get("element_id")
                return result
        candidate.status = "applied"
        candidate.applied_at = datetime.utcnow()
        candidate.destination = "memory"
        candidate.vector_chunk_id = None
        if feedback_id:
            feedback = session.get(FabricFeedbackRecord, feedback_id)
            if feedback:
                feedback.status = "applied"
        result = _candidate_dict(candidate)

    fabric = fabric_store.get(fabric_id) or {"id": fabric_id, "name": fabric_id}
    facts = [fact for fact in list(fabric.get("memory_facts") or []) if isinstance(fact, dict)]
    facts.append({
        "candidate_id": candidate_id,
        "fact": proposed,
        "query": query,
        "applied_at": result.get("applied_at"),
        "vector_chunk_id": None,
        "destination": "memory",
    })
    fabric["memory_facts"] = facts[-100:]
    fabric["memory_fact_count"] = len([fact for fact in facts if not fact.get("retired_at")])
    fabric["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    fabric_store.save(fabric)
    result["fabric_memory_fact_count"] = fabric["memory_fact_count"]
    return result


def retire_memory_fact(fabric_id: str, candidate_id: str) -> Dict[str, Any]:
    """Stop injecting an approved memory override. The source row is unchanged."""
    fabric = fabric_store.get(fabric_id) or {"id": fabric_id}
    facts = []
    found = False
    for fact in list(fabric.get("memory_facts") or []):
        if isinstance(fact, dict) and fact.get("candidate_id") == candidate_id and not fact.get("retired_at"):
            fact = dict(fact)
            fact["retired_at"] = datetime.utcnow().isoformat()
            found = True
        facts.append(fact)
    if not found:
        raise ValueError("Approved memory fact not found")
    fabric["memory_facts"] = facts
    fabric["memory_fact_count"] = len([fact for fact in facts if isinstance(fact, dict) and not fact.get("retired_at")])
    fabric["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    fabric_store.save(fabric)
    return {"candidate_id": candidate_id, "retired": True, "memory_fact_count": fabric["memory_fact_count"]}


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
    return [f for f in facts if isinstance(f, dict) and not f.get("retired_at")]


def promote_memory_fact(fabric_id: str, candidate_id: str) -> Dict[str, Any]:
    """Propose an approved override as an ontology alias or rule. Memory stays until approval."""
    from app.services.context.classifier import classify_correction

    fact = next((item for item in approved_facts(fabric_id) if item.get("candidate_id") == candidate_id), None)
    if not fact:
        raise ValueError("Approved memory fact not found")
    text = str(fact.get("fact") or "").strip()
    ctx = _context_for_classification(fabric_id, None)
    classification = ctx["classify"](
        text,
        classes=ctx["classes"],
        attributes=ctx["attributes"],
        columns=ctx["columns"],
    )
    destination = classification.get("destination")
    if destination not in {"ontology_alias", "ontology_constraint"}:
        forced = classify_correction(text, scope="ontology_constraint")
        if not text:
            raise ValueError("This override has no text to promote")
        destination = "ontology_constraint"
        classification = forced
        classification["reason"] = (
            "Sent to the ontology draft as a rule. It stays fabric memory until that version is approved."
        )
    submitted = submit_feedback(
        fabric_id=fabric_id,
        rating="down",
        correction_text=text,
        scope=destination,
    )
    submitted["promoted_from"] = candidate_id
    submitted["classification_reason"] = classification.get("reason")
    return submitted


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
        "destination": row.destination or "memory",
        "classification_reason": row.classification_reason,
        "classification": row.classification,
        "vector_chunk_id": row.vector_chunk_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "applied_at": row.applied_at.isoformat() if row.applied_at else None,
    }
