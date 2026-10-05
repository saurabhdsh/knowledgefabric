"""Session memory, episodic log, and closed-loop fabric rewrite."""
from datetime import datetime, timedelta

from app.db.models import AgentSessionRecord
from app.db.session import db_session, init_db
from app.services import agent_memory_service


def test_session_remembers_prior_turn():
    first = agent_memory_service.record_exchange(
        fabric_id="fabric_memory_test",
        query="How many claims are denied?",
        answer="Denied: 10",
        llm_provider="deterministic",
    )
    second = agent_memory_service.record_exchange(
        fabric_id="fabric_memory_test",
        query="Break that down by payer",
        answer="Aetna: 4, UHC: 6",
        session_id=first["session_id"],
        llm_provider="deterministic",
    )
    assert second["session_id"] == first["session_id"]
    turns = agent_memory_service.list_turns(first["session_id"], limit=10)
    assert [t["role"] for t in turns] == ["user", "assistant", "user", "assistant"]
    context = agent_memory_service.build_query_context("fabric_memory_test", first["session_id"])
    assert "How many claims are denied?" in context
    assert "RECENT CONVERSATION" in context


def test_negative_feedback_queues_then_rewrites_fabric(monkeypatch):
    recorded = agent_memory_service.record_exchange(
        fabric_id="fabric_memory_test",
        query="What does status mean?",
        answer="It is unknown.",
    )
    saved = {}

    def fake_add_documents(documents, fabric_id):
        assert fabric_id == "fabric_memory_test"
        assert documents[0]["metadata"]["chunk_type"] == "memory_fact"
        return ["chunk_memory_1"]

    def fake_get(fabric_id):
        return {"id": fabric_id, "name": "Claims", "total_chunks": 3, "memory_facts": []}

    def fake_save(fabric):
        saved.update(fabric)
        return fabric

    monkeypatch.setattr(agent_memory_service, "_index_memory_fact", fake_add_documents)
    monkeypatch.setattr(agent_memory_service.fabric_store, "get", fake_get)
    monkeypatch.setattr(agent_memory_service.fabric_store, "save", fake_save)

    feedback = agent_memory_service.submit_feedback(
        fabric_id="fabric_memory_test",
        episode_id=recorded["episode_id"],
        session_id=recorded["session_id"],
        rating="down",
        outcome="incorrect",
        correction_text="status means adjudication_status",
    )
    assert feedback["status"] == "queued"
    applied = agent_memory_service.approve_candidate(feedback["enrichment_candidate_id"])
    assert applied["status"] == "applied"
    assert applied["vector_chunk_id"] == "chunk_memory_1"
    assert saved["memory_facts"][0]["fact"] == "status means adjudication_status"
    assert saved["total_chunks"] == 4

    context = agent_memory_service.build_query_context("fabric_memory_test", None)
    # build_query_context reads fabric_store.get, which is still the fake returning empty facts.
    # Confirm the saved payload is what future reads would inject.
    monkeypatch.setattr(
        agent_memory_service.fabric_store,
        "get",
        lambda fabric_id: saved,
    )
    context = agent_memory_service.build_query_context("fabric_memory_test", None)
    assert "APPROVED FABRIC MEMORY" in context
    assert "adjudication_status" in context


def test_expired_session_is_hidden():
    init_db()
    created = agent_memory_service.create_session("fabric_memory_test", title="old")
    with db_session() as session:
        rec = session.get(AgentSessionRecord, created["session_id"])
        rec.expires_at = datetime.utcnow() - timedelta(hours=2)
    assert agent_memory_service.get_session(created["session_id"]) is None
