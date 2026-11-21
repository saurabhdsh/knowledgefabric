"""Phase 3 — composite as a real join: entity links, hybrid routing, shared ontology, refresh."""
from __future__ import annotations

import json
import uuid

import pytest

from app.services.fabric_pipeline.composite_ontology import choose_shared_ontology_project
from app.services.fabric_pipeline.entity_resolution import (
    extract_candidate_mentions,
    link_document_chunks,
    load_entity_links,
)
from app.services.fabric_pipeline.query import answer_query, classify_query_intent, looks_narrative
from app.services.fabric_pipeline.table_store import table_store
from app.services.platform.fabric_store import fabric_store
from tests.pdf_factory import PdfBuilder


def _dataset():
    members = [
        {
            "member_id": f"MEM-{i:04d}",
            "member_name": f"Person {i}",
            "age": 30 + i,
            "plan_id": "PLN-A",
            "pcp_provider_id": "PRV-01",
            "active": "true",
            "dob": "1970-01-15",
            "ndc": f"001{i:04d}",
            "network_id": "NET-1",
        }
        for i in range(1, 11)
    ]
    # Make Lisa-like member for name matching
    members[6]["member_name"] = "Lisa Chen"
    members[6]["member_id"] = "MEM-LISA-01"
    plans = [{"plan_id": "PLN-A", "plan_name": "Gold", "premium": "$100", "network_id": "NET-1"}]
    providers = [{"provider_id": "PRV-01", "provider_name": "Clinic 1", "network_id": "NET-1"}]
    claims = [
        {
            "claim_id": f"CLM-{i:05d}",
            "member_id": members[i % len(members)]["member_id"],
            "provider_id": "PRV-01",
            "service_date": "2026-01-10",
            "paid_amount": f"{50 + i}.00",
            "claim_type": "Outpatient",
        }
        for i in range(1, 21)
    ]
    return {"members": members, "plans": plans, "providers": providers, "claims": claims}


def _record(name, source_type):
    return {"name": name, "source_type": source_type, "description": "", "tags": []}


def _care_plan_pdf(path: str) -> None:
    """PDF that names a member so Phase 3 entity resolution can join to the table store."""
    b = PdfBuilder()
    b.heading("Care Plan", 18)
    b.heading("Member Follow-up", 14)
    b.paragraph(
        "Care manager notes for Lisa Chen (member MEM-LISA-01). "
        "Follow the outreach policy exclusions when scheduling the 48-hour follow-up."
    )
    with open(path, "wb") as fh:
        fh.write(b.build())


class FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, messages, max_tokens, temperature):
        self.calls.append(messages)
        if not self.replies:
            return "OK"
        return self.replies.pop(0)


def _embedding_model_or_skip():
    from app.services.embedding_service import EmbeddingUnavailableError, get_embedding_model

    try:
        model = get_embedding_model()
        model.embed(["warm up"])
        return model
    except EmbeddingUnavailableError as exc:  # pragma: no cover
        pytest.skip(f"embedding model unavailable: {exc}")


@pytest.fixture()
def pipeline_env(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.db.session import init_db
    from app.services.platform.fabric_store import fabric_store
    from app.services.vector_service import vector_service

    _embedding_model_or_skip()
    monkeypatch.setattr(settings, "FABRIC_TABLES_DIR", str(tmp_path / "tables"))
    monkeypatch.setattr(settings, "FABRIC_MANIFEST_DIR", str(tmp_path / "manifests"))
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    init_db()
    fabric_store.initialize()
    created = []
    yield created
    for fid in created:
        vector_service.delete_source_documents(fid)
        try:
            from app.db.models import FabricJobRecord
            from app.db.session import db_session
            with db_session() as session:
                session.query(FabricJobRecord).filter(FabricJobRecord.fabric_id == fid).delete()
        except Exception:
            pass
        fabric_store.delete(fid)


# --------------------------------------------------------------------------
# Intent classification
# --------------------------------------------------------------------------


def test_classify_intent_structured_narrative_mixed():
    profile = {"tables": [{"name": "members", "columns": [{"name": "age", "role": "measure"}]}]}
    assert classify_query_intent("How many members are enrolled?", profile) == "structured"
    assert looks_narrative("who is left out of the outreach program")
    assert classify_query_intent("who is left out of the outreach program", profile) == "narrative"
    assert classify_query_intent(
        "How many members are eligible according to the outreach policy?",
        profile,
    ) == "mixed"


def test_extract_mentions_finds_ids_and_names():
    ids, names = extract_candidate_mentions(
        "Care manager notes for Lisa Chen (member MEM-LISA-01)."
    )
    assert "MEM-LISA-01" in ids
    assert any("Lisa Chen" == n or "Lisa" in n for n in names)


# --------------------------------------------------------------------------
# End-to-end composite
# --------------------------------------------------------------------------


def test_phase3_entity_links_hybrid_shared_ontology_and_refresh(pipeline_env, tmp_path, monkeypatch):
    from app.core.config import settings
    from app.services.fabric_pipeline.pipelines import (
        refresh_composite_pipeline,
        run_composite_pipeline,
        run_document_pipeline,
        run_tabular_pipeline,
    )
    from app.services.fabric_pipeline.runner import load_manifest

    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)

    dataset = _dataset()
    a, b, c, comp = (f"fabric_p3_{uuid.uuid4().hex[:8]}" for _ in range(4))
    pipeline_env.extend([a, b, c, comp])

    members = run_tabular_pipeline(
        fabric_id=a,
        record=_record("Members DB", "database"),
        tables={k: dataset[k] for k in ("members", "plans", "providers")},
    )
    # Pretend members already have an approved ontology project (shared ontology input)
    members["ontology_project_id"] = "proj_shared_p3"
    members["approved_ontology_version_id"] = "ver_shared_p3"
    fabric_store.save(members)

    claims = run_tabular_pipeline(
        fabric_id=b,
        record=_record("Claims DB", "database"),
        tables={"claims": dataset["claims"]},
    )
    claims["ontology_project_id"] = "proj_shared_p3"
    fabric_store.save(claims)

    path = str(tmp_path / "care_plan.pdf")
    _care_plan_pdf(path)
    policy = run_document_pipeline(
        fabric_id=c,
        record=_record("Care Plan PDF", "pdf"),
        files=[{"path": path, "original_name": "Care Plan.pdf", "stored_name": "cp.pdf", "size": 1, "sha256": None}],
    )

    # Shared ontology choice before create
    choice = choose_shared_ontology_project(
        {"id": comp, "name": "Join"},
        [fabric_store.get(a), fabric_store.get(b), fabric_store.get(c)],
    )
    assert choice["project_id"] == "proj_shared_p3"
    assert choice["strategy"] == "reuse_shared_source_project"

    fabric = run_composite_pipeline(
        fabric_id=comp,
        sources=[fabric_store.get(a), fabric_store.get(b), fabric_store.get(c)],
        record={"name": "P3 Join", "source_type": "composite", "description": "", "tags": ["composite"]},
    )
    assert fabric["status"] == "active" and fabric["has_table_store"]
    assert fabric["entity_links"]["link_count"] >= 1
    links = load_entity_links(comp)
    values = {str(L.get("value")) for L in links.get("links") or []}
    assert "MEM-LISA-01" in values or "Lisa Chen" in values

    # Structured → sql (plan JSON + prose answer)
    llm_sql = FakeLLM([
        json.dumps({
            "sql": "SELECT COUNT(*) AS n FROM members",
            "explanation": "count members",
        }),
        "There are 10 members.",
    ])
    out_sql = answer_query(fabric, "How many members are there?", llm=llm_sql, system_prompt="s")
    assert out_sql["route"] == "sql"
    assert out_sql.get("intent") == "structured"

    # Narrative → retrieval with origin prefix
    llm_doc = FakeLLM(["Follow the outreach policy exclusions."])
    out_doc = answer_query(
        fabric,
        "who is left out of the outreach program according to the care plan",
        llm=llm_doc,
        system_prompt="s",
    )
    assert out_doc["intent"] == "narrative"
    assert out_doc["route"] in ("retrieval", "entity+retrieval", "linked+retrieval")
    refs = [c["reference"] for c in out_doc["citations"]]
    assert any("Care Plan PDF" in r or "Care Plan.pdf" in r for r in refs)

    # Mixed → hybrid: SQL plan + SQL prose + final hybrid answer
    llm_mix = FakeLLM([
        json.dumps({"sql": "SELECT COUNT(*) AS n FROM members", "explanation": "count"}),
        "10",
        "10 members; follow outreach exclusions in the care plan [1].",
    ])
    out_mix = answer_query(
        fabric,
        "How many members are eligible according to the outreach policy?",
        llm=llm_mix,
        system_prompt="s",
    )
    assert out_mix["intent"] == "mixed"
    assert out_mix["route"] == "hybrid"
    assert out_mix.get("sql")
    assert out_mix["citations"]

    # Refresh keeps id, rebuilds from live sources
    before_chunks = fabric["total_chunks"]
    # Touch a source name so refresh has something to copy again
    src_a = fabric_store.get(a)
    src_a["name"] = "Members DB refreshed"
    fabric_store.save(src_a)
    refreshed = refresh_composite_pipeline(fabric_id=comp)
    assert refreshed["id"] == comp
    assert refreshed["status"] == "active"
    assert refreshed["total_chunks"] >= before_chunks - 5  # rebuilt
    assert refreshed.get("last_refreshed_at")
    assert refreshed["entity_links"]["link_count"] >= 1
    manifest = load_manifest(comp)
    assert any(
        "entity_links" in (st.get("metrics") or {})
        for st in manifest.get("stages") or []
    )
