"""Name links: a name is weaker evidence than an identifier and is treated that way."""
from __future__ import annotations

import pytest

from app.services.fabric_pipeline import tabular_profiler
from app.services.fabric_pipeline.entity_resolution import (
    linked_row_context_for_chunks,
    resolve_mentions_against_profile,
)
from app.services.fabric_pipeline.table_store import TableStore, assign_sql_names
from app.services.fabric_pipeline.tabular_query import (
    CONFIDENCE_AMBIGUOUS_NAME,
    CONFIDENCE_IDENTIFIER,
    CONFIDENCE_NAME_AND_FACT,
    CONFIDENCE_UNIQUE_NAME,
    entity_context_text,
    find_entities,
    rows_by_reference,
)

FABRIC = "fab_names"


def _tables():
    members = [
        {"member_id": f"MEM-{i:04d}", "member_name": f"Person {i}", "dob": f"19{50 + i % 40}-0{1 + i % 9}-1{i % 9}",
         "plan_id": "PLN-A"}
        for i in range(1, 31)
    ]
    # Two different people with the same name and different birth dates.
    members.append({"member_id": "MEM-9001", "member_name": "Lisa Chen", "dob": "1961-03-15", "plan_id": "PLN-A"})
    members.append({"member_id": "MEM-9002", "member_name": "Lisa Chen", "dob": "1988-11-02", "plan_id": "PLN-B"})
    members.append({"member_id": "MEM-9003", "member_name": "Omar Haddad", "dob": "1975-06-30", "plan_id": "PLN-B"})
    providers = [{"provider_id": f"PRV-{i:03d}", "provider_name": f"Clinic {i}"} for i in range(1, 25)]
    providers.append({"provider_id": "PRV-900", "provider_name": "Hope"})
    plans = [
        {"plan_id": "PLN-A", "plan_name": "Gold"},
        {"plan_id": "PLN-B", "plan_name": "Silver"},
    ]
    return {"members": members, "providers": providers, "plans": plans}


@pytest.fixture()
def env(tmp_path):
    tables = _tables()
    profile = tabular_profiler.profile_tables(tables)
    assign_sql_names(profile)
    store = TableStore(str(tmp_path / "tables"))
    store.build(FABRIC, tables, profile)
    return profile, store


def _ids(found):
    return sorted(e["row"].get("member_id") or e["row"].get("provider_id") for e in found)


def test_identifier_links_at_full_confidence(env):
    profile, store = env
    found = resolve_mentions_against_profile(FABRIC, profile, "Care plan for MEM-9001, reviewed in May.", store)
    assert _ids(found) == ["MEM-9001"]
    assert found[0]["basis"] == "identifier" and found[0]["confidence"] == CONFIDENCE_IDENTIFIER == 1.0


def test_unique_name_links_below_an_identifier(env):
    profile, store = env
    found = resolve_mentions_against_profile(FABRIC, profile, "Visit note for Omar Haddad after discharge.", store)
    assert _ids(found) == ["MEM-9003"]
    assert found[0]["basis"] == "unique_name"
    assert found[0]["confidence"] == CONFIDENCE_UNIQUE_NAME < CONFIDENCE_IDENTIFIER


def test_shared_name_links_no_row_and_is_reported(env):
    profile, store = env
    unclear = []
    found = resolve_mentions_against_profile(
        FABRIC, profile, "Lisa Chen was seen for a COPD flare-up.", store, ambiguous_out=unclear
    )
    assert found == []
    assert unclear == [{"name": "lisa chen", "row_count": 2, "tables": ["members"]}]


@pytest.mark.parametrize("text", [
    "Lisa Chen (DOB 03/15/1961) was seen for a COPD flare-up.",
    "Lisa Chen, born March 15, 1961, was seen for a COPD flare-up.",
    "Patient: Lisa Chen. Date of birth: 1961-03-15.",
])
def test_shared_name_links_when_a_birth_date_agrees(env, text):
    profile, store = env
    found = resolve_mentions_against_profile(FABRIC, profile, text, store)
    assert _ids(found) == ["MEM-9001"]
    assert found[0]["basis"] == "name_and_second_fact" and found[0]["second_fact"] == "dob"
    assert found[0]["confidence"] == CONFIDENCE_NAME_AND_FACT


def test_identifier_in_the_text_settles_a_shared_name(env):
    profile, store = env
    found = resolve_mentions_against_profile(FABRIC, profile, "Lisa Chen (MEM-9002) called about a bill.", store)
    assert _ids(found) == ["MEM-9002"]
    assert found[0]["basis"] == "identifier"


@pytest.mark.parametrize("text", [
    "We hope the member recovers quickly.",
    "Hope is not a treatment plan. The member needs follow-up.",   # capital only because it opens a sentence
    "The gold standard of care applies here.",                     # a plan is called Gold
])
def test_common_words_are_not_names(env, text):
    profile, store = env
    assert resolve_mentions_against_profile(FABRIC, profile, text, store) == []


def test_a_single_word_name_links_when_written_as_a_name(env):
    profile, store = env
    found = resolve_mentions_against_profile(FABRIC, profile, "The member was referred to Hope for imaging.", store)
    assert _ids(found) == ["PRV-900"]
    assert found[0]["basis"] == "unique_name"


def test_misspelled_name_is_not_guessed(env):
    profile, store = env
    assert resolve_mentions_against_profile(FABRIC, profile, "Omar Hadad was discharged.", store) == []


def test_question_about_a_shared_name_shows_every_row_marked_ambiguous(env):
    profile, store = env
    found = find_entities(FABRIC, profile, "What plan is Lisa Chen on?", store)
    assert _ids(found) == ["MEM-9001", "MEM-9002"]
    assert {e["basis"] for e in found} == {"ambiguous_name"}
    assert {e["confidence"] for e in found} == {CONFIDENCE_AMBIGUOUS_NAME}
    text = entity_context_text(found)
    assert "one of 2 rows with this name" in text and "exact lookup" not in text


def test_stored_link_is_followed_to_exactly_its_row(env):
    profile, store = env
    # A link made from name + birth date keeps the row's key, so reading it
    # back returns that member and not the other Lisa Chen.
    chunks = [{
        "id": "c1", "content": "Lisa Chen, born March 15, 1961.",
        "metadata": {"linked_entities_json": (
            '[{"table": "members", "column": "member_name", "value": "Lisa Chen", '
            '"key_column": "member_id", "key_value": "MEM-9001", "confidence": 0.9, '
            '"basis": "name_and_second_fact"}]'
        )},
    }]
    context = linked_row_context_for_chunks(FABRIC, profile, chunks, store)
    assert "MEM-9001" in context and "MEM-9002" not in context
    # A link that only kept the shared name selects two rows, so it is not followed.
    assert rows_by_reference(
        FABRIC, profile, [{"table": "members", "column": "member_name", "value": "Lisa Chen"}], store
    ) == []
