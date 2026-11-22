"""Auth hardening: password rule, lockout, revocation, API-key path past JWT."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import (
    LOCKOUT_THRESHOLD,
    MIN_PASSWORD_LENGTH,
    auth_service,
)
from app.services.inbound_api_key_service import inbound_api_key_service


SEED_USER = "Saurabh"
SEED_PASS = "admin123"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_AUTH_DISABLED", "0")
    monkeypatch.setenv("INBOUND_AUTH_DISABLED", "0")
    key_file = tmp_path / "inbound_keys.json"
    monkeypatch.setenv("KF_INBOUND_KEYS_FILE", str(key_file))
    inbound_api_key_service.store_path = str(key_file)
    from app.db.session import init_db

    init_db()
    auth_service.ensure_seed_users()
    # Reset seed password hash to the known first-login value for every test.
    user = auth_service.get_user_by_username(SEED_USER)
    assert user is not None
    from app.db.session import db_session
    from app.db.models import UserRecord

    with db_session() as session:
        row = session.get(UserRecord, user.id)
        row.password_hash = auth_service.hash_password(SEED_PASS)
        row.must_change_password = True
        row.failed_login_count = 0
        row.locked_until = None
        session.flush()
    return TestClient(app)


def test_password_rule_rejects_short_and_simple():
    with pytest.raises(ValueError):
        auth_service.validate_password("short")
    with pytest.raises(ValueError):
        auth_service.validate_password("alllowercase1")
    auth_service.validate_password("GoodPass1!")


def test_seed_login_then_must_change_password(client):
    res = client.post("/api/v1/auth/login", json={"username": SEED_USER, "password": SEED_PASS})
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["user"]["must_change_password"] is True
    token = body["data"]["access_token"]

    bad = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": SEED_PASS, "new_password": "short"},
    )
    assert bad.status_code in (400, 422)

    ok = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": SEED_PASS, "new_password": "NewPass1!xx"},
    )
    assert ok.status_code == 200
    assert ok.json()["data"]["user"]["must_change_password"] is False


def test_failed_logins_lock_the_account(client):
    user = auth_service.create_user(
        username="lockme",
        password="TempPass1!x",
        display_name="Lock Me",
        role="user",
    )
    from app.db.session import db_session
    from app.db.models import UserRecord

    with db_session() as session:
        row = session.get(UserRecord, user.id)
        row.must_change_password = False
        row.failed_login_count = 0
        row.locked_until = None
        session.flush()

    for _ in range(LOCKOUT_THRESHOLD):
        res = client.post("/api/v1/auth/login", json={"username": "lockme", "password": "wrong"})
        assert res.status_code == 401

    locked = client.post("/api/v1/auth/login", json={"username": "lockme", "password": "TempPass1!x"})
    assert locked.status_code == 423


def test_logout_revokes_session(client):
    res = client.post("/api/v1/auth/login", json={"username": SEED_USER, "password": SEED_PASS})
    token = res.json()["data"]["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    after = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert after.status_code == 401


def test_api_key_passes_jwt_layer_with_fabric_scope(client):
    _record, plain = inbound_api_key_service.issue(
        name="partner",
        scopes=["query", "read"],
        fabric_ids=["fab_allowed"],
    )
    ok = client.get(
        "/api/v1/knowledge/fab_allowed/relationships",
        headers={"X-API-Key": plain},
    )
    assert ok.status_code != 401

    denied = client.get(
        "/api/v1/knowledge/fab_other/relationships",
        headers={"X-API-Key": plain},
    )
    assert denied.status_code == 403


def test_password_min_length_constant():
    assert MIN_PASSWORD_LENGTH >= 10
