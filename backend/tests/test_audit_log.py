from sqlalchemy import select

from app.models.audit_log import AuditLog
from tests.helpers import register_and_login


def test_successful_register_and_login_are_audited(client, db_session):
    register_and_login(client, email="audit-success@example.com")

    entries = db_session.execute(select(AuditLog).order_by(AuditLog.created_at)).scalars().all()
    actions = [(e.action, e.status) for e in entries]

    assert ("register", "success") in actions
    assert ("login", "success") in actions
    # Every successful entry must be attributed to the user it belongs to.
    for entry in entries:
        if entry.status == "success":
            assert entry.user_id is not None


def test_failed_login_is_audited_without_leaking_which_check_failed(client, db_session):
    client.post(
        "/api/v1/auth/register", json={"email": "audit-fail@example.com", "password": "correct-password-1"}
    )
    response = client.post(
        "/api/v1/auth/login", json={"email": "audit-fail@example.com", "password": "wrong-password"}
    )
    assert response.status_code == 401

    entries = db_session.execute(select(AuditLog).where(AuditLog.action == "login")).scalars().all()
    failures = [e for e in entries if e.status == "failure"]
    assert len(failures) == 1
    # No metadata should distinguish "wrong password" from "unknown email" —
    # that distinction helps account enumeration, so it must never be logged.
    assert failures[0].event_metadata == {}


def test_duplicate_registration_is_audited_as_failure(client, db_session):
    payload = {"email": "audit-dupe@example.com", "password": "strongpassword123"}
    client.post("/api/v1/auth/register", json=payload)
    second = client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409

    entries = db_session.execute(select(AuditLog).where(AuditLog.action == "register")).scalars().all()
    statuses = [e.status for e in entries]
    assert statuses.count("success") == 1
    assert statuses.count("failure") == 1


def test_token_refresh_is_audited(client, db_session):
    client.post("/api/v1/auth/register", json={"email": "audit-refresh@example.com", "password": "strongpassword123"})
    login_response = client.post(
        "/api/v1/auth/login", json={"email": "audit-refresh@example.com", "password": "strongpassword123"}
    ).json()

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": login_response["refresh_token"]})
    assert refreshed.status_code == 200

    entries = db_session.execute(select(AuditLog).where(AuditLog.action == "token_refresh")).scalars().all()
    assert len(entries) == 1
    assert entries[0].status == "success"
    assert entries[0].user_id is not None
