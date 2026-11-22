"""Release 2.0 — Phase 0 and Phase 1: embeddings, profiling, table store, parsing, pipelines.

These tests use the real embedding model and the real vector store configured
for the process. Run them in an isolated environment (temporary KF_* dirs and a
SQLite DATABASE_URL); every fabric they create is removed again.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid

import pytest

from app.core.config import settings
from app.services.fabric_pipeline import tabular_profiler
from app.services.fabric_pipeline.chunker import chunk_document, citation, split_sentences
from app.services.fabric_pipeline.document_parser import (
    DocumentParseError,
    ocr_available,
    parse_document,
    parse_pdf,
)
from app.services.fabric_pipeline.table_store import (
    SqlNotAllowedError,
    TableStore,
    assign_sql_names,
    validate_select,
)
from app.services.fabric_pipeline.tabular_index import build_index_documents, sql_schema_text
from app.services.fabric_pipeline.tabular_query import answer_with_sql, entity_context_text, find_entities
from tests.pdf_factory import PdfBuilder, scanned_pdf


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


def _dataset():
    members = [
        {"member_id": f"MEM-{i:04d}", "member_name": f"Person {i}", "age": 30 + (i % 50),
         "plan_id": "PLN-A" if i % 3 else "PLN-B", "pcp_provider_id": f"PRV-{i % 4:02d}",
         "active": "true" if i % 5 else "false", "dob": f"19{60 + i % 30}-0{1 + i % 9}-15",
         "ndc": f"00{17300 + i}", "network_id": "NET-1" if i % 2 else "NET-2"}
        for i in range(1, 41)
    ]
    plans = [
        {"plan_id": "PLN-A", "plan_name": "Gold", "premium": "$1,180.00", "network_id": "NET-1"},
        {"plan_id": "PLN-B", "plan_name": "Silver", "premium": "$940.50", "network_id": "NET-1"},
    ]
    providers = [
        {"provider_id": f"PRV-{i:02d}", "provider_name": f"Clinic {i}", "network_id": "NET-1" if i % 2 else "NET-2"}
        for i in range(4)
    ]
    claims = []
    n = 0
    for i in range(1, 41):
        for j in range(i % 4):  # 0..3 claims per member
            n += 1
            claims.append({
                "claim_id": f"CLM-{n:05d}", "member_id": f"MEM-{i:04d}", "provider_id": f"PRV-{(i + j) % 4:02d}",
                "service_date": f"2026-0{1 + j}-1{j}", "paid_amount": f"{100 * (j + 1) + i}.50",
                "claim_type": ["Inpatient", "Outpatient", "ER"][j % 3],
            })
    return {"members": members, "plans": plans, "providers": providers, "claims": claims}


@pytest.fixture()
def dataset():
    return _dataset()


@pytest.fixture()
def profile(dataset):
    p = tabular_profiler.profile_tables(dataset)
    assign_sql_names(p)
    return p


@pytest.fixture()
def store(tmp_path, dataset, profile):
    s = TableStore(str(tmp_path / "tables"))
    s.build("fab_test", dataset, profile)
    return s


def _embedding_model_or_skip():
    from app.services.embedding_service import EmbeddingUnavailableError, get_embedding_model

    try:
        model = get_embedding_model()
        model.embed(["warm up"])
        return model
    except EmbeddingUnavailableError as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"embedding model unavailable: {exc}")


# --------------------------------------------------------------------------
# Phase 0 — embeddings
# --------------------------------------------------------------------------


def test_embeddings_are_semantic_and_normalised():
    model = _embedding_model_or_skip()
    assert model.semantic and model.dim == 384
    a, b, c = model.embed([
        "shortness of breath and a lung disease flare-up",
        "COPD exacerbation",
        "quarterly revenue forecast for the retail division",
    ])
    dot = lambda x, y: sum(p * q for p, q in zip(x, y))
    assert abs(dot(a, a) - 1.0) < 1e-4
    assert dot(a, b) > dot(a, c) + 0.2  # related text is closer, by meaning not shared words


def test_embeddings_are_identical_across_processes():
    """The 1.x hash embedding changed on every restart; this must not."""
    _embedding_model_or_skip()
    code = (
        "import json;from app.services.embedding_service import get_embedding_model;"
        "print(json.dumps(get_embedding_model().embed(['member cost of care'])[0][:8]))"
    )
    outs = []
    for seed in ("1", "987"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, check=True)
        outs.append(json.loads(res.stdout.strip().splitlines()[-1]))
    assert outs[0] == pytest.approx(outs[1], abs=1e-6)


def test_embedding_info_names_model_and_collection():
    model = _embedding_model_or_skip()
    info = model.info()
    assert info["id"] and info["dimension"] == 384 and info["collection"].startswith("kf_")
    assert info["revision"]


# --------------------------------------------------------------------------
# Phase 1 — profiler
# --------------------------------------------------------------------------


def test_profiler_infers_types_strictly(profile):
    members = tabular_profiler.table_by_name(profile, "members")
    types = {c["name"]: c["type"] for c in members["columns"]}
    assert types["age"] == "integer"
    assert types["active"] == "boolean"
    assert types["dob"] == "date"
    assert types["ndc"] == "string"          # leading zeros: an identifier, not a number
    assert types["member_id"] == "string"
    plans = tabular_profiler.table_by_name(profile, "plans")
    premium = next(c for c in plans["columns"] if c["name"] == "premium")
    assert premium["type"] == "float" and premium["parsed_from"] == "currency"
    assert premium["max"] == 1180.0


def test_profiler_mixed_column_stays_text_and_nulls_counted():
    rows = [{"id": str(i), "v": v} for i, v in enumerate(["1", "2", "x", "", None, "NaN"], start=1)]
    p = tabular_profiler.profile_tables({"t": rows})
    v = next(c for c in p["tables"][0]["columns"] if c["name"] == "v")
    assert v["type"] == "string"
    assert v["null_count"] == 3 and v["null_rate"] == 0.5


def test_profiler_finds_keys(profile):
    keys = {t["name"]: t["primary_key"] for t in profile["tables"]}
    assert keys == {
        "members": ["member_id"], "plans": ["plan_id"],
        "providers": ["provider_id"], "claims": ["claim_id"],
    }


def test_profiler_finds_foreign_keys_by_value_overlap(profile):
    fks = {(f["from_table"], f["from_column"]): (f["to_table"], f["to_column"]) for f in profile["foreign_keys"]}
    assert fks[("claims", "member_id")] == ("members", "member_id")
    assert fks[("claims", "provider_id")] == ("providers", "provider_id")
    assert fks[("members", "plan_id")] == ("plans", "plan_id")
    # Name differs from the parent key; found because the values are the parent's keys.
    assert fks[("members", "pcp_provider_id")] == ("providers", "provider_id")
    # network_id repeats in every table but is unique in none: not a key, so no relationship.
    assert not any(col == "network_id" for (_, col) in fks)
    # age (30..79) must never be matched to anything.
    assert ("members", "age") not in fks
    for f in profile["foreign_keys"]:
        assert f["overlap"] >= settings.FABRIC_FK_MIN_OVERLAP


def test_profiler_rejects_integer_lookalike_foreign_key():
    orders = [{"order_id": i, "quantity": (i % 5) + 1} for i in range(1, 101)]
    items = [{"item_id": i, "label": f"item {i}"} for i in range(1, 31)]
    p = tabular_profiler.profile_tables({"orders": orders, "items": items})
    # quantity values (1..5) are all valid item ids, but nothing says it is a reference.
    assert not any(f["from_column"] == "quantity" for f in p["foreign_keys"])


def test_profiler_reports_orphans_and_samples():
    parents = [{"dept_id": f"D{i}", "dept_name": f"Dept {i}"} for i in range(1, 31)]
    children = [{"emp_id": f"E{i}", "dept_id": f"D{(i % 30) + 1}"} for i in range(1, 300)]
    children.append({"emp_id": "E999", "dept_id": "D-MISSING"})
    p = tabular_profiler.profile_tables({"departments": parents, "employees": children}, {"employees": 5000, "departments": 30})
    fk = next(f for f in p["foreign_keys"] if f["from_table"] == "employees")
    assert fk["orphan_values"] == 1 and fk["overlap"] < 1.0
    emp = tabular_profiler.table_by_name(p, "employees")
    assert emp["is_sample"] and emp["source_row_count"] == 5000
    assert p["summary"]["is_sample"]
    assert any("sample" in w for w in p["warnings"])
    assert any("no matching parent" in w for w in p["warnings"])


def test_profiler_classifies_tables(profile):
    kinds = {t["name"]: t["kind"] for t in profile["tables"]}
    assert kinds["members"] == "entity" and kinds["plans"] == "entity" and kinds["providers"] == "entity"
    assert kinds["claims"] == "fact"


# --------------------------------------------------------------------------
# Phase 1 — table store and SQL guard
# --------------------------------------------------------------------------


def test_table_store_holds_typed_rows_and_answers_aggregates(store, dataset):
    expected_total = sum(float(c["paid_amount"]) for c in dataset["claims"])
    result = store.query("fab_test", "SELECT COUNT(*), SUM(paid_amount) FROM claims")
    assert result["rows"][0][0] == len(dataset["claims"])
    assert result["rows"][0][1] == pytest.approx(expected_total)
    joined = store.query(
        "fab_test",
        "SELECT p.plan_name, COUNT(*) FROM claims c JOIN members m ON m.member_id = c.member_id "
        "JOIN plans p ON p.plan_id = m.plan_id GROUP BY p.plan_name ORDER BY 1",
    )
    by_plan = {}
    plan_of = {m["member_id"]: m["plan_id"] for m in dataset["members"]}
    for c in dataset["claims"]:
        name = "Gold" if plan_of[c["member_id"]] == "PLN-A" else "Silver"
        by_plan[name] = by_plan.get(name, 0) + 1
    assert {r[0]: r[1] for r in joined["rows"]} == by_plan
    # booleans are 1/0, leading-zero codes survive intact
    assert store.query("fab_test", "SELECT COUNT(*) FROM members WHERE active = 1")["rows"][0][0] == 32
    assert store.query("fab_test", "SELECT ndc FROM members WHERE member_id = 'MEM-0001'")["rows"][0][0] == "0017301"


@pytest.mark.parametrize("sql", [
    "DELETE FROM claims",
    "UPDATE claims SET paid_amount = 0",
    "DROP TABLE claims",
    "INSERT INTO plans VALUES ('x','y',1,'z')",
    "SELECT 1; DROP TABLE claims",
    "PRAGMA table_info(claims)",
    "ATTACH DATABASE '/tmp/x.db' AS x",
    "WITH t AS (SELECT 1) DELETE FROM claims",
    "",
])
def test_sql_guard_rejects_anything_but_one_select(store, sql):
    with pytest.raises(SqlNotAllowedError):
        store.query("fab_test", sql)
    assert store.query("fab_test", "SELECT COUNT(*) FROM claims")["rows"][0][0] > 0


def test_sql_guard_allows_keywords_inside_string_literals(store):
    assert validate_select("SELECT 'drop table x; delete' AS note")
    result = store.query("fab_test", "SELECT COUNT(*) FROM claims WHERE claim_type = 'update; delete'")
    assert result["rows"][0][0] == 0


def test_sql_authorizer_blocks_schema_table_and_store_is_read_only(store):
    with pytest.raises(Exception):
        store.query("fab_test", "SELECT name FROM sqlite_master")
    with pytest.raises(SqlNotAllowedError):
        store.query("fab_test", "SELECT load_extension('x')")


def test_sql_row_cap_reports_truncation(store, dataset):
    result = store.query("fab_test", "SELECT claim_id FROM claims", max_rows=10)
    assert len(result["rows"]) == 10 and result["truncated"] is True
    full = store.query("fab_test", "SELECT claim_id FROM claims", max_rows=10_000)
    assert len(full["rows"]) == len(dataset["claims"]) and full["truncated"] is False


def test_reserved_and_messy_names_are_made_queryable(tmp_path):
    rows = [{"Order": i, "Group": "g", "Total Amount ($)": "5.5", "2nd": "x"} for i in range(1, 25)]
    p = tabular_profiler.profile_tables({"Select": rows})
    assign_sql_names(p)
    s = TableStore(str(tmp_path / "t"))
    s.build("f", {"Select": rows}, p)
    t = p["tables"][0]
    names = {c["name"]: c["sql_name"] for c in t["columns"]}
    assert t["sql_name"] == "select_" and names["Order"] == "order_" and names["Total Amount ($)"] == "total_amount"
    total = s.query("f", f'SELECT SUM({names["Total Amount ($)"]}) FROM {t["sql_name"]}')["rows"][0][0]
    assert total == pytest.approx(5.5 * 24)


# --------------------------------------------------------------------------
# Phase 1 — what gets embedded for tabular data
# --------------------------------------------------------------------------


def test_tabular_index_embeds_summaries_not_rows(store, profile, dataset):
    docs, stats = build_index_documents("fab_test", "Test", profile, store)
    types = [d["metadata"]["chunk_type"] for d in docs]
    assert "row" not in types
    assert types.count("dataset") == 1 and types.count("schema") == 4
    # entity tables are summarised; the fact table (claims) is not turned into chunks
    assert stats["entity_summaries"] == {"members": 40, "plans": 2, "providers": 4}
    assert len(docs) < sum(len(v) for v in dataset.values())
    member = next(d for d in docs if d["metadata"].get("row_key") == "MEM-0003")
    text = member["content"]
    assert "Member MEM-0003 (Person 3)" in text
    assert "plan id: PLN-B (Silver)" in text                 # parent label resolved through the FK
    expected = [c for c in dataset["claims"] if c["member_id"] == "MEM-0003"]
    total = sum(float(c["paid_amount"]) for c in expected)
    assert f"{len(expected)} claims (total paid amount {total:g})" in text


def test_sql_schema_text_uses_sql_names_and_relationships(profile):
    text = sql_schema_text(profile)
    assert "Table claims:" in text and "claims.member_id -> members.member_id" in text
    assert "stored as 1/0" in text


# --------------------------------------------------------------------------
# Phase 1 — entity lookup and SQL answers
# --------------------------------------------------------------------------


def test_entity_lookup_by_id_expands_through_foreign_keys(store, profile, dataset):
    found = find_entities("fab_test", profile, "What is going on with MEM-0007?", store)
    assert len(found) == 1 and found[0]["table"] == "members"
    entity = found[0]
    assert entity["row"]["member_name"] == "Person 7"
    parents = {p["table"] for p in entity["parents"]}
    assert parents == {"plans", "providers"}
    claims = next(c for c in entity["children"] if c["table"] == "claims")
    expected = [c for c in dataset["claims"] if c["member_id"] == "MEM-0007"]
    assert claims["total"] == len(expected)
    assert claims["sums"]["paid_amount"] == pytest.approx(sum(float(c["paid_amount"]) for c in expected))
    text = entity_context_text(found)
    assert "exact lookup" in text and "<- claims" in text and "-> plans" in text


def test_entity_lookup_by_name_and_no_false_match_on_plain_numbers(store, profile):
    found = find_entities("fab_test", profile, "Tell me about Person 12 please", store)
    assert [e["row"]["member_id"] for e in found] == ["MEM-0012"]
    assert find_entities("fab_test", profile, "top 5 members in 2026", store) == []


class FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, messages, max_tokens, temperature):
        self.calls.append(messages)
        return self.replies.pop(0)


def test_answer_with_sql_runs_the_planned_query_over_all_rows(store, profile, dataset):
    llm = FakeLLM([
        json.dumps({"sql": "SELECT claim_type, COUNT(*) AS claims FROM claims GROUP BY claim_type ORDER BY 2 DESC",
                    "explanation": "claims per type"}),
        "ER has the fewest claims.",
    ])
    result = answer_with_sql("fab_test", "Test", profile, "How many claims per type?", llm, store)
    counts = {}
    for c in dataset["claims"]:
        counts[c["claim_type"]] = counts.get(c["claim_type"], 0) + 1
    assert {r[0]: r[1] for r in result["rows"]} == counts
    assert result["answer"] == "ER has the fewest claims."
    assert "GROUP BY" in result["sql"]
    # the planner saw the real schema; the writer saw the real result
    assert "Table claims:" in llm.calls[0][1]["content"]
    assert str(max(counts.values())) in llm.calls[1][1]["content"]


def test_answer_with_sql_retries_once_then_reports_failure(store, profile):
    llm = FakeLLM([
        json.dumps({"sql": "SELECT nope FROM claims", "explanation": "bad"}),
        "```json\n" + json.dumps({"sql": "SELECT COUNT(*) AS n FROM claims", "explanation": "count"}) + "\n```",
        "There are claims.",
    ])
    ok = answer_with_sql("fab_test", "Test", profile, "How many claims?", llm, store)
    assert ok["answer"] == "There are claims." and len(ok["attempts"]) == 2
    assert "no such column" in ok["attempts"][0]["error"]

    destructive = FakeLLM([json.dumps({"sql": "DROP TABLE claims", "explanation": "x"})] * 2)
    bad = answer_with_sql("fab_test", "Test", profile, "How many claims?", destructive, store)
    assert bad["answer"] is None and "only select" in bad["error"].lower()
    assert store.query("fab_test", "SELECT COUNT(*) FROM claims")["rows"][0][0] > 0


def test_answer_with_sql_returns_none_when_planner_declines(store, profile):
    llm = FakeLLM([json.dumps({"sql": None, "explanation": "needs judgement"})])
    assert answer_with_sql("fab_test", "Test", profile, "What should we do?", llm, store) is None


# --------------------------------------------------------------------------
# Phase 1 — layout-aware PDF parsing and chunking
# --------------------------------------------------------------------------

LONG = (
    "Chronic obstructive pulmonary disease is managed with a combination of inhaled therapy, "
    "pulmonary rehabilitation and vaccination. Exacerbations are the main driver of admissions. "
    "Patients who miss two consecutive refills are flagged for pharmacist outreach within 48 hours. "
)


def _sample_pdf(path):
    b = PdfBuilder()
    b.heading("Care Management Policy", 20)
    b.paragraph("This policy describes how the care team manages members with chronic conditions.")
    b.heading("1 Eligibility", 14)
    b.paragraph("Members enrolled in the Gold plan with two or more admissions are eligible. " + LONG)
    b.heading("1.1 Exclusions", 12)
    b.paragraph("Members in hospice care are excluded from outreach.")
    b.new_page()
    b.heading("2 Cost Benchmarks", 14)
    b.paragraph("The table lists the annual benchmark per condition.")
    b.table([["Condition", "Benchmark", "Tier"], ["COPD", "48750", "High"], ["Asthma", "9120", "Low"], ["CHF", "61200", "High"]])
    b.paragraph("Benchmarks are reviewed every quarter by the finance committee.")
    b.new_page()
    b.heading("3 Escalation", 14)
    b.paragraph(LONG * 6)
    b.footer_all("Confidential - Care Policy v3")
    with open(path, "wb") as fh:
        fh.write(b.build())


def test_pdf_parse_finds_headings_tables_and_real_pages(tmp_path):
    path = str(tmp_path / "policy.pdf")
    _sample_pdf(path)
    parsed = parse_pdf(path, "Care Policy.pdf")
    assert parsed["page_count"] == 3 and parsed["stats"]["pages_unreadable"] == 0
    headings = [(b["text"], b["page"]) for b in parsed["blocks"] if b["type"] == "heading"]
    assert headings == [
        ("Care Management Policy", 1), ("1 Eligibility", 1), ("1.1 Exclusions", 1),
        ("2 Cost Benchmarks", 2), ("3 Escalation", 3),
    ]
    level = {b["text"]: b["level"] for b in parsed["blocks"] if b["type"] == "heading"}
    assert level["Care Management Policy"] < level["1 Eligibility"] < level["1.1 Exclusions"]
    assert level["1 Eligibility"] == level["2 Cost Benchmarks"] == level["3 Escalation"]
    tables = [b for b in parsed["blocks"] if b["type"] == "table"]
    assert len(tables) == 1 and tables[0]["page"] == 2
    assert "| Condition | Benchmark | Tier |" in tables[0]["text"] and "| COPD | 48750 | High |" in tables[0]["text"]
    # table cells are not repeated as loose paragraph text
    paragraphs = " ".join(b["text"] for b in parsed["blocks"] if b["type"] == "paragraph")
    assert "48750" not in paragraphs
    # the repeated footer and page numbers are dropped
    assert "Confidential" not in paragraphs and "Confidential" not in " ".join(h[0] for h in headings)
    assert parsed["stats"]["paragraphs"] >= 6


def test_chunks_follow_structure_and_carry_citations(tmp_path):
    path = str(tmp_path / "policy.pdf")
    _sample_pdf(path)
    parsed = parse_pdf(path, "Care Policy.pdf")
    chunks = chunk_document(parsed, max_chars=700)

    table = [c for c in chunks if c["block_type"] == "table"]
    assert len(table) == 1 and table[0]["page_start"] == 2
    assert table[0]["section_path"] == "Care Management Policy > 2 Cost Benchmarks"

    excl = next(c for c in chunks if "hospice" in c["body"])
    assert excl["section_path"] == "Care Management Policy > 1 Eligibility > 1.1 Exclusions"
    assert excl["content"].startswith("[Care Policy.pdf > Care Management Policy > 1 Eligibility > 1.1 Exclusions]")
    assert "Eligible" not in excl["body"] and "eligible" not in excl["body"]   # no bleed across headings

    escalation = [c for c in chunks if c["section_path"].endswith("3 Escalation")]
    assert len(escalation) >= 2 and all(c["page_start"] == 3 for c in escalation)
    for c in escalation:
        assert len(c["content"]) <= 700 + 40
        assert c["body"].rstrip().endswith((".", "!", "?"))            # never cut mid-sentence
    assert citation({"page_start": 2, "page_end": 2, "section_path": "2 Cost Benchmarks", "block_type": "table"},
                    "Care Policy.pdf") == "Care Policy.pdf, p. 2, 2 Cost Benchmarks, table"


def test_sentence_splitter_keeps_abbreviations_together():
    parts = split_sentences("Use inhalers, e.g. Trelegy. Dr. Ortiz reviews it. Done!")
    assert parts == ["Use inhalers, e.g. Trelegy.", "Dr. Ortiz reviews it.", "Done!"]


def test_scanned_pdf_is_read_by_ocr_or_reported_unreadable(tmp_path, monkeypatch):
    path = str(tmp_path / "scan.pdf")
    if not scanned_pdf(path, ["Discharge Summary", "Patient was stabilized on oxygen", "Follow up in seven days"]):
        pytest.skip("Pillow cannot render sized text here")

    can_ocr, _ = ocr_available()
    if can_ocr:
        parsed = parse_pdf(path, "scan.pdf")
        text = " ".join(b["text"] for b in parsed["blocks"]).lower()
        assert parsed["stats"]["pages_ocr"] == 1
        assert "stabilized" in text and "oxygen" in text and "seven days" in text
        assert all(b["ocr"] for b in parsed["blocks"])

    # With OCR off, the scan must fail loudly, not produce an empty fabric.
    monkeypatch.setattr(settings, "PDF_OCR_ENABLED", False)
    with pytest.raises(DocumentParseError) as err:
        parse_pdf(path, "scan.pdf")
    assert "no extractable text" in str(err.value) and "OCR" in str(err.value)


def test_text_file_headings_and_unsupported_type(tmp_path):
    p = tmp_path / "notes.md"
    p.write_text("# Title\n\nFirst paragraph here.\n\n## Part A\n\nBody of part A.\n", encoding="utf-8")
    parsed = parse_document(str(p), "notes.md")
    chunks = chunk_document(parsed)
    assert [c["section_path"] for c in chunks] == ["Title", "Title > Part A"]
    assert all(c["page_start"] is None for c in chunks)
    bad = tmp_path / "x.docx"
    bad.write_bytes(b"zz")
    with pytest.raises(DocumentParseError):
        parse_document(str(bad), "x.docx")


# --------------------------------------------------------------------------
# Phase 1 — full pipelines (real embeddings, real index, real fabric store)
# --------------------------------------------------------------------------


@pytest.fixture()
def pipeline_env(tmp_path, monkeypatch):
    _embedding_model_or_skip()
    monkeypatch.setattr(settings, "FABRIC_TABLES_DIR", str(tmp_path / "tables"))
    monkeypatch.setattr(settings, "FABRIC_MANIFEST_DIR", str(tmp_path / "manifests"))
    from app.db.session import init_db
    from app.services.platform.fabric_store import fabric_store
    from app.services.vector_service import vector_service

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


def _record(name, source_type):
    return {"name": name, "source_type": source_type, "description": "test", "tags": ["test"]}


def test_tabular_pipeline_end_to_end(pipeline_env, dataset):
    from app.services.fabric_pipeline.pipelines import run_tabular_pipeline
    from app.services.fabric_pipeline.query import answer_query
    from app.services.fabric_pipeline.runner import load_manifest
    from app.services.fabric_pipeline.table_store import table_store
    from app.services.platform.fabric_store import fabric_store
    from app.services.platform.job_service import job_service
    from app.services.vector_service import vector_service

    fid = f"fabric_t_{uuid.uuid4().hex[:8]}"
    pipeline_env.append(fid)
    fabric = run_tabular_pipeline(
        fabric_id=fid, tables=dataset, record=_record("Claims Test", "database"),
        source_row_counts={"claims": 5000, "members": 40, "plans": 2, "providers": 4},
    )
    assert fabric["status"] == "active" and fabric["model_status"] == "indexed"
    assert fabric["pipeline_version"] == 2 and fabric["has_table_store"]
    assert fabric["embedding"]["id"] == vector_service.embedding_info()["id"]
    assert fabric["is_sample"] and fabric["rows_in_source"] == 5046
    assert fabric["row_count"] == sum(len(v) for v in dataset.values())
    claims_info = next(t for t in fabric["connection_info"]["per_collection"] if t["name"] == "claims")
    assert claims_info["rows_in_source"] == 5000 and claims_info["is_sample"]
    assert [s["name"] for s in fabric["pipeline"]["stages"]] == ["profile", "parse", "model", "index", "validate", "publish"]
    assert all(s["status"] == "completed" for s in fabric["pipeline"]["stages"])

    stored = fabric_store.get(fid)
    assert stored["status"] == "active"
    manifest = load_manifest(fid)
    assert manifest["status"] == "completed" and manifest["profile"]["summary"]["foreign_key_count"] == 4
    checks = {c["check"]: c["status"] for c in manifest["stages"][4]["metrics"]["checks"]}
    assert checks["row_counts"] == "pass" and checks["numeric_integrity"] == "pass"
    assert checks["index_count"] == "pass" and checks["index_roundtrip"] == "pass"
    assert any("sample" in w["message"] for w in manifest["warnings"])
    job = job_service.get(manifest["job_id"])
    assert job["status"] == "ready" and job["job_type"] == "fabric_ingest" and job["progress_percent"] == 100.0

    # rows are in the table store, not in the vector index
    assert table_store.row_counts(fid)["claims"] == len(dataset["claims"])
    assert vector_service.count_source_documents(fid) == fabric["total_chunks"] < fabric["row_count"]

    # computed answer: SQL over all rows, statement returned
    llm = FakeLLM([
        json.dumps({"sql": "SELECT SUM(paid_amount) AS total_paid FROM claims", "explanation": "total paid"}),
        "TOTAL",
    ])
    out = answer_query(stored, "What is the total paid amount?", llm=llm, system_prompt="s")
    assert out["route"] == "sql" and out["confidence"] is None
    assert out["analytics"]["rows"][0][0] == pytest.approx(sum(float(c["paid_amount"]) for c in dataset["claims"]))
    assert out["analytics"]["is_sample"] is True and "sample" in out["confidence_basis"]

    # record question: exact lookup + semantic retrieval, cited
    llm2 = FakeLLM(["ANSWER"])
    out2 = answer_query(stored, "Summarise MEM-0007 for me", llm=llm2, system_prompt="s")
    assert out2["route"] == "entity+retrieval" and out2["entities"][0]["value"] == "MEM-0007"
    prompt = llm2.calls[0][1]["content"]
    assert "EXACT RECORD LOOKUP" in prompt and "Person 7" in prompt and "DATASET OVERVIEW" in prompt
    # Phase 4 fuses lexical and vector scores; the ranker names both and the embedding model.
    assert out2["retrieval"]["ranker"].startswith("hybrid+vector:")
    # the chunk that contains the identifier is first, ahead of merely similar summaries
    assert out2["citations"][0]["reference"].startswith("members MEM-0007")
    # Phase 4 may label the fused hit as exact-token or semantic; the identifier still leads.
    assert out2["citations"][0]["match"] in {"exact-token", "semantic", "hybrid"}
    assert out2["retrieval"]["exact_token_chunks"] >= 0

    # no LLM: the rule engine still computes over all rows; evidence is returned otherwise
    out3 = answer_query(stored, "How many claims are there?", llm=None, system_prompt="s")
    assert out3["route"] in ("rules", "evidence-only")
    if out3["route"] == "rules":
        assert str(len(dataset["claims"])) in out3["answer"].replace(",", "")


def test_tabular_pipeline_failure_marks_fabric_failed(pipeline_env):
    from app.services.fabric_pipeline.pipelines import run_tabular_pipeline
    from app.services.fabric_pipeline.runner import PipelineError, load_manifest
    from app.services.fabric_pipeline.table_store import table_store
    from app.services.platform.fabric_store import fabric_store
    from app.services.platform.job_service import job_service
    from app.services.vector_service import vector_service

    fid = f"fabric_t_{uuid.uuid4().hex[:8]}"
    pipeline_env.append(fid)
    with pytest.raises(PipelineError) as err:
        run_tabular_pipeline(fabric_id=fid, tables={"empty": []}, record=_record("Empty", "database"))
    assert err.value.stage == "profile" and err.value.fabric_id == fid
    stored = fabric_store.get(fid)
    assert stored["status"] == "failed" and stored["model_status"] == "failed" and "no rows" in stored["error"]
    manifest = load_manifest(fid)
    assert manifest["status"] == "failed" and manifest["error"]["stage"] == "profile"
    assert job_service.get(manifest["job_id"])["status"] == "failed"
    assert not table_store.exists(fid) and vector_service.count_source_documents(fid) == 0


def test_index_failure_leaves_no_half_built_fabric(pipeline_env, dataset, monkeypatch):
    from app.services.fabric_pipeline.pipelines import run_tabular_pipeline
    from app.services.fabric_pipeline.runner import PipelineError
    from app.services.fabric_pipeline.table_store import table_store
    from app.services.platform.fabric_store import fabric_store
    from app.services.vector_service import vector_service

    def boom(texts):
        raise RuntimeError("embedding backend down")

    monkeypatch.setattr(vector_service, "create_embeddings", boom)
    fid = f"fabric_t_{uuid.uuid4().hex[:8]}"
    pipeline_env.append(fid)
    with pytest.raises(PipelineError) as err:
        run_tabular_pipeline(fabric_id=fid, tables=dataset, record=_record("Boom", "database"))
    assert err.value.stage == "index"
    stored = fabric_store.get(fid)
    assert stored["status"] == "failed" and "embedding backend down" in stored["error"]
    assert not table_store.exists(fid)


def test_isolated_collection_search_uses_embeddings(pipeline_env, monkeypatch):
    """Per-fabric indexes are still embedding indexes. Search must not fall back to BM25."""
    monkeypatch.setattr(settings, "ISOLATE_FABRIC_INDEX", True)
    from app.services.vector_service import vector_service

    fid = f"fabric_iso_{uuid.uuid4().hex[:8]}"
    pipeline_env.append(fid)
    vector_service.add_documents(
        [
            {"content": "Hospice members are excluded from the outreach program.", "source_name": "t", "file_name": "t.pdf"},
            {"content": "The COPD annual benchmark amount is 48750.", "source_name": "t", "file_name": "t.pdf"},
        ],
        fid,
    )
    hits = vector_service.search_similar_chunks("who is left out of the outreach program", fid, top_k=2)
    assert hits and str(hits[0]["ranker"]).startswith("vector:")
    info = vector_service.source_embedding_info(fid)
    assert info["needs_reindex"] is False


def test_document_pipeline_end_to_end(pipeline_env, tmp_path):
    from app.services.fabric_pipeline.pipelines import run_document_pipeline
    from app.services.fabric_pipeline.query import answer_query
    from app.services.fabric_pipeline.runner import PipelineError, load_manifest
    from app.services.platform.fabric_store import fabric_store
    from app.services.vector_service import vector_service

    path = str(tmp_path / "abc123.pdf")
    _sample_pdf(path)
    fid = f"fabric_d_{uuid.uuid4().hex[:8]}"
    pipeline_env.append(fid)
    files = [{"path": path, "original_name": "Care Policy.pdf", "stored_name": "abc123.pdf", "size": 1, "sha256": None}]
    fabric = run_document_pipeline(fabric_id=fid, files=files, record=_record("Care Policy", "pdf"))
    assert fabric["status"] == "active" and fabric["page_count"] == 3 and fabric["document_count"] == 1
    assert fabric["processed_files"][0]["original_name"] == "Care Policy.pdf"
    assert fabric["processed_files"][0]["filename"] == fabric["processed_files"][0]["stored_name"]
    assert fabric["processed_files"][0]["tables"] == 1
    manifest = load_manifest(fid)
    assert manifest["inputs"]["files"][0]["sha256"] and manifest["outline"]["Care Policy.pdf"][0]["title"] == "Care Management Policy"
    doc_checks = {c["check"]: c for c in manifest["stages"][4]["metrics"]["checks"]}
    assert doc_checks["index_roundtrip"]["status"] == "pass" and doc_checks["index_count"]["status"] == "pass"
    assert "recall" in doc_checks["retrieval_recall"]

    # a paraphrased question (no shared keywords with "hospice ... excluded") finds the right passage and page
    hits = vector_service.search_similar_chunks("who is left out of the outreach program", fid, top_k=3)
    assert hits[0]["ranker"].startswith("vector:")
    assert any("hospice" in h["content"] for h in hits)
    bench = vector_service.search_similar_chunks("annual benchmark amount for COPD", fid, top_k=3)
    table_hit = next(h for h in bench if h["metadata"].get("block_type") == "table")
    assert table_hit["metadata"]["page_start"] == 2 and "48750" in table_hit["content"]

    llm = FakeLLM(["ANSWER [1]"])
    out = answer_query(fabric_store.get(fid), "who is left out of the outreach program", llm=llm, system_prompt="s")
    assert out["route"] == "retrieval" and 0 < out["confidence"] <= 1
    assert any("p. 1" in c["reference"] and "1.1 Exclusions" in c["reference"] for c in out["citations"])
    assert "(Care Policy.pdf, p. 1" in llm.calls[0][1]["content"]

    # an unreadable file fails the whole build and names the file
    empty = tmp_path / "empty.txt"
    empty.write_text("   \n", encoding="utf-8")
    fid2 = f"fabric_d_{uuid.uuid4().hex[:8]}"
    pipeline_env.append(fid2)
    with pytest.raises(PipelineError) as err:
        run_document_pipeline(
            fabric_id=fid2,
            files=files + [{"path": str(empty), "original_name": "empty.txt", "stored_name": "e.txt", "size": 4, "sha256": None}],
            record=_record("Bad", "pdf"),
        )
    assert "empty.txt" in str(err.value) and err.value.stage == "parse"
    assert fabric_store.get(fid2)["status"] == "failed"
    assert vector_service.count_source_documents(fid2) == 0


def test_composite_pipeline_discovers_cross_source_relationships(pipeline_env, dataset, tmp_path):
    from app.services.fabric_pipeline.pipelines import run_composite_pipeline, run_document_pipeline, run_tabular_pipeline
    from app.services.fabric_pipeline.query import answer_query
    from app.services.fabric_pipeline.runner import load_manifest
    from app.services.fabric_pipeline.table_store import table_store

    a, b, c, comp = (f"fabric_c_{uuid.uuid4().hex[:8]}" for _ in range(4))
    pipeline_env.extend([a, b, c, comp])
    members = run_tabular_pipeline(
        fabric_id=a, record=_record("Members DB", "database"),
        tables={k: dataset[k] for k in ("members", "plans", "providers")},
    )
    claims = run_tabular_pipeline(fabric_id=b, record=_record("Claims DB", "database"), tables={"claims": dataset["claims"]})
    # on its own the claims fabric cannot know what member_id refers to
    assert load_manifest(b)["profile"]["foreign_keys"] == []

    path = str(tmp_path / "p.pdf")
    _sample_pdf(path)
    policy = run_document_pipeline(
        fabric_id=c, record=_record("Policy", "pdf"),
        files=[{"path": path, "original_name": "Care Policy.pdf", "stored_name": "p.pdf", "size": 1, "sha256": None}],
    )

    fabric = run_composite_pipeline(
        fabric_id=comp, sources=[members, claims, policy],
        record={"name": "Everything", "source_type": "composite", "description": "", "tags": []},
    )
    assert fabric["status"] == "active" and fabric["has_table_store"]
    manifest = load_manifest(comp)
    cross = manifest["stages"][2]["metrics"]["cross_source_relationships"]
    assert any(r.startswith("claims.member_id -> members.member_id") for r in cross)
    assert any(r.startswith("claims.provider_id -> providers.provider_id") for r in cross)
    assert table_store.row_counts(comp)["claims"] == len(dataset["claims"])
    assert fabric["composite_metadata"]["copied_chunks"] == policy["total_chunks"]

    # one question, both kinds of source: a join across the two databases...
    llm = FakeLLM([
        json.dumps({"sql": "SELECT m.member_name, SUM(c.paid_amount) AS paid FROM claims c JOIN members m "
                           "ON m.member_id = c.member_id GROUP BY m.member_name ORDER BY paid DESC LIMIT 1",
                    "explanation": "top member by paid amount"}),
        "TOP",
    ])
    out = answer_query(fabric, "Which member has the highest total paid amount?", llm=llm, system_prompt="s")
    totals = {}
    for cl in dataset["claims"]:
        totals[cl["member_id"]] = totals.get(cl["member_id"], 0.0) + float(cl["paid_amount"])
    best = max(totals, key=totals.get)
    assert out["route"] == "sql" and out["analytics"]["rows"][0][0] == f"Person {int(best[-4:])}"

    # ...and the policy document, cited back to its source fabric and page
    llm2 = FakeLLM(["DOC"])
    out2 = answer_query(fabric, "who is left out of the outreach program", llm=llm2, system_prompt="s")
    refs = [c["reference"] for c in out2["citations"]]
    assert refs[0] == "Policy: Care Policy.pdf, p. 1, Care Management Policy > 1 Eligibility > 1.1 Exclusions"
