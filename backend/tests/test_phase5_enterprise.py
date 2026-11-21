"""Phase 5: lineage, incremental sync, PII, access, isolated index names."""
from __future__ import annotations

import os
import sqlite3

import pytest

from app.core.user_context import current_user_id
from app.services.enterprise.ops import (
    AccessDenied,
    authorize,
    classify_pii,
    isolated_collection_name,
    on_publish,
    plan_row_sync,
    record_grant,
    redact_row,
)
from app.services.fabric_pipeline.table_store import table_store


def test_pii_marks_member_identity_and_leaves_amounts():
    tagged = {row["column"]: row["sensitivity"] for row in classify_pii(
        ["member_id", "member_name", "ytd_total_cost", "email"]
    )}
    assert tagged["member_id"] == "phi"
    assert tagged["member_name"] == "phi"
    assert tagged["email"] == "pii"
    assert tagged["ytd_total_cost"] == "none"


def test_incremental_plan_and_schema_change():
    current = [{"member_id": "M1", "risk": "Low"}, {"member_id": "M2", "risk": "High"}]
    incoming = [
        {"member_id": "M1", "risk": "High"},
        {"member_id": "M3", "risk": "Low"},
    ]
    plan = plan_row_sync(
        current,
        incoming,
        key_columns=["member_id"],
        current_columns=["member_id", "risk"],
        incoming_columns=["member_id", "risk"],
    )
    assert plan["mode"] == "incremental"
    assert plan["added_count"] == 1
    assert plan["changed_count"] == 1
    assert plan["removed_count"] == 1
    rebuild = plan_row_sync(
        current,
        [{"member_id": "M1", "risk": "Low", "state": "TX"}],
        key_columns=["member_id"],
        current_columns=["member_id", "risk"],
        incoming_columns=["member_id", "risk", "state"],
    )
    assert rebuild["mode"] == "full_rebuild"


def test_apply_row_delta_updates_sqlite(tmp_path, monkeypatch):
    monkeypatch.setattr(table_store, "_root", str(tmp_path))
    fabric_id = "fabric_phase5_delta"
    path = table_store.path(fabric_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE members (member_id TEXT, risk TEXT)')
    conn.execute("INSERT INTO members VALUES ('M1', 'Low'), ('M2', 'High')")
    conn.commit()
    conn.close()
    current = table_store.rows(fabric_id, "members")
    incoming = [{"member_id": "M1", "risk": "High"}, {"member_id": "M3", "risk": "Low"}]
    plan = plan_row_sync(current, incoming, key_columns=["member_id"])
    table_store.apply_row_delta(fabric_id, "members", ["member_id", "risk"], ["member_id"], plan)
    rows = {r["member_id"]: r["risk"] for r in table_store.rows(fabric_id, "members")}
    assert rows == {"M1": "High", "M3": "Low"}


def test_lineage_links_parent_and_isolates_index(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.enterprise.ops.settings.DATA_DIR", str(tmp_path))
    fabric = {
        "id": "fabric_phase5_lineage",
        "owner_id": "usr_owner",
        "row_count": 2,
        "connection_info": {"tables": [{"name": "members", "columns": [{"name": "member_id"}, {"name": "member_name"}]}]},
    }
    first = on_publish(fabric)
    second = on_publish(fabric, change="sync")
    assert second["parent_id"] == first["id"]
    assert fabric["pii"]["sensitive"]
    assert fabric["index_collection"] == isolated_collection_name(fabric["id"])
    assert isolated_collection_name(fabric["id"]).startswith("kf_f_")


def test_access_control_and_redaction():
    fabric = {
        "id": "fabric_acl",
        "owner_id": "usr_owner",
        "access": {"owner_id": "usr_owner", "grants": [{"user_id": "usr_owner", "role": "owner"}]},
    }
    token = current_user_id.set("usr_viewer")
    try:
        with pytest.raises(AccessDenied):
            authorize(fabric, "query")
    finally:
        current_user_id.reset(token)
    record_grant(fabric, "usr_viewer", "viewer")
    token = current_user_id.set("usr_viewer")
    try:
        assert authorize(fabric, "query") == "viewer"
        with pytest.raises(AccessDenied):
            authorize(fabric, "export")
        with pytest.raises(AccessDenied):
            authorize(fabric, "sync")
    finally:
        current_user_id.reset(token)
    hidden = redact_row({"member_name": "Lisa Chen", "risk_tier": "High"}, ["member_name"])
    assert hidden["member_name"] == "[restricted]"
    assert hidden["risk_tier"] == "High"
