"""Context envelope lines round-trip, and the episode stores the packet."""
from app.services import agent_memory_service
from app.services.context.envelope import begin_envelope, finish_envelope, render_memory, render_ontology


def test_ontology_and_memory_render_back_to_the_same_prompt_text():
    ontology = "\n".join([
        "Domain ontology (approved): Members have claims",
        "Graph facts:",
        "- Lisa Chen has 10 claims",
        "Linked entity: Lisa Chen (mem-lisa-copd)",
    ])
    memory = (
        "APPROVED FABRIC MEMORY (these corrections override earlier answers):\n"
        "- Care manager is Anita Shah\n\n"
        "RECENT CONVERSATION (short-term session memory):\n"
        "User: Who is Lisa?\n"
        "Assistant: Lisa Chen, MEM-LISA-COPD."
    )
    envelope = begin_envelope(memory, ontology, "ver_917a33a1a14d")
    assert render_ontology(envelope) == ontology
    assert render_memory(envelope) == memory
    kinds = [line["kind"] for line in envelope["lines"]]
    assert kinds == ["ontology", "graph", "graph", "memory", "session", "session"]
    assert envelope["lines"][0]["source_id"] == "ver_917a33a1a14d"
    assert envelope["lines"][3]["confidence"] == 1.0
    assert "prompt_ontology" not in envelope
    assert "prompt_memory" not in envelope


def test_finish_envelope_adds_table_and_passage_without_dropping_contract_lines():
    envelope = begin_envelope("", "Domain ontology (approved): Members", "ver_1")
    finished = finish_envelope(
        envelope,
        route="hybrid",
        confidence=0.86,
        measurement={"confidence": 0.86, "sql_backed": True},
        sql="SELECT COUNT(*) FROM members",
        table_text="520 members",
        chunks=[{"id": "chunk-1", "content": "Care plan policy", "rerank_score": 0.71}],
    )
    assert [line["kind"] for line in finished["lines"]] == ["ontology", "table", "passage"]
    assert finished["route"] == "hybrid"
    assert finished["measurement"]["sql_backed"] is True
    assert finished["lines"][2]["source_id"] == "chunk-1"
    assert render_ontology(finished) == "Domain ontology (approved): Members"


def test_episode_stores_the_envelope():
    envelope = finish_envelope(
        begin_envelope(
            "APPROVED FABRIC MEMORY (these corrections override earlier answers):\n- Call within 14 days",
            "Domain ontology (approved): Avoidable ER needs a care plan",
            "ver_917a33a1a14d",
        ),
        route="hybrid",
        confidence=0.9,
        table_text="Lisa Chen has an ER event",
        sql="SELECT 1",
    )
    recorded = agent_memory_service.record_exchange(
        fabric_id="fabric_context_envelope",
        query="Should we outreach Lisa Chen this week?",
        answer="Yes. Call the care manager.",
        route="hybrid",
        ontology_version_id="ver_917a33a1a14d",
        confidence=0.9,
        context_envelope=envelope,
    )
    stored = agent_memory_service.get_episode(recorded["episode_id"])
    assert stored["route"] == "hybrid"
    assert stored["ontology_version_id"] == "ver_917a33a1a14d"
    assert stored["confidence"] == 0.9
    kinds = [line["kind"] for line in stored["context_envelope"]["lines"]]
    assert kinds == ["ontology", "memory", "table"]
    assert stored["context_envelope"]["lines"][0]["text"] == "Avoidable ER needs a care plan"
