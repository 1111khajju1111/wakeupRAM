from datetime import datetime, timedelta, timezone

from tests.helpers import register_and_login


def _create_countdown(client, headers, **overrides):
    payload = {
        "title": "Board exam",
        "target_datetime": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
    }
    payload.update(overrides)
    return client.post("/api/v1/countdowns", json=payload, headers=headers)


def test_create_and_list_countdown(client):
    headers = register_and_login(client)

    response = _create_countdown(client, headers, title="Hackathon submission")
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Hackathon submission"
    assert body["is_active"] is True
    assert body["priority"] == "medium"
    assert body["repeat_rule"] == "none"
    # Defaults come from the model, not a hardcoded schedule per-countdown,
    # but every countdown still needs *some* configured offsets.
    assert body["notification_offsets_minutes"] == [1440, 60]

    countdowns = client.get("/api/v1/countdowns", headers=headers).json()
    assert len(countdowns) == 1


def test_no_countdown_exists_until_the_user_creates_one(client):
    """Section 17: countdowns are completely user-created. A brand-new user
    must see an empty list, never a seeded/demo countdown."""
    headers = register_and_login(client)

    countdowns = client.get("/api/v1/countdowns", headers=headers).json()
    assert countdowns == []


def test_update_and_deactivate_countdown(client):
    headers = register_and_login(client)
    countdown_id = _create_countdown(client, headers).json()["id"]

    response = client.patch(
        f"/api/v1/countdowns/{countdown_id}", json={"title": "Updated title", "priority": "high"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated title"
    assert response.json()["priority"] == "high"

    response = client.patch(f"/api/v1/countdowns/{countdown_id}", json={"is_active": False}, headers=headers)
    assert response.json()["is_active"] is False

    active_only = client.get("/api/v1/countdowns?active_only=true", headers=headers).json()
    assert active_only == []


def test_delete_countdown(client):
    headers = register_and_login(client)
    countdown_id = _create_countdown(client, headers).json()["id"]

    response = client.delete(f"/api/v1/countdowns/{countdown_id}", headers=headers)
    assert response.status_code == 204

    assert client.get("/api/v1/countdowns", headers=headers).json() == []


def test_invalid_priority_is_rejected(client):
    headers = register_and_login(client)

    response = _create_countdown(client, headers, priority="urgent")
    assert response.status_code == 422


def _parse_aware(value: str) -> datetime:
    # The test database (SQLite) doesn't round-trip tzinfo the way
    # production Postgres does, so a naive value here means UTC.
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def test_daily_repeat_rolls_target_forward_once_passed(client):
    headers = register_and_login(client)
    past_target = datetime.now(timezone.utc) - timedelta(hours=3)

    countdown_id = _create_countdown(
        client, headers, title="Daily review", target_datetime=past_target.isoformat(), repeat_rule="daily"
    ).json()["id"]

    response = client.get(f"/api/v1/countdowns/{countdown_id}", headers=headers)
    rolled_target = _parse_aware(response.json()["target_datetime"])
    assert rolled_target > datetime.now(timezone.utc)


def test_non_repeating_countdown_stays_in_the_past_once_passed(client):
    headers = register_and_login(client)
    past_target = datetime.now(timezone.utc) - timedelta(hours=3)

    countdown_id = _create_countdown(
        client, headers, target_datetime=past_target.isoformat(), repeat_rule="none"
    ).json()["id"]

    response = client.get(f"/api/v1/countdowns/{countdown_id}", headers=headers)
    target = _parse_aware(response.json()["target_datetime"])
    assert target < datetime.now(timezone.utc)


def test_today_view_surfaces_the_soonest_active_countdown(client):
    headers = register_and_login(client)
    soon = datetime.now(timezone.utc) + timedelta(hours=2)
    later = datetime.now(timezone.utc) + timedelta(days=30)

    _create_countdown(client, headers, title="Later thing", target_datetime=later.isoformat())
    _create_countdown(client, headers, title="Soon thing", target_datetime=soon.isoformat())

    today = client.get("/api/v1/today", headers=headers).json()
    assert today["active_countdown"]["title"] == "Soon thing"


def test_user_cannot_access_another_users_countdown(client):
    headers_a = register_and_login(client, email="a@example.com")
    headers_b = register_and_login(client, email="b@example.com")

    countdown_id = _create_countdown(client, headers_a, title="A's private deadline").json()["id"]

    assert client.get("/api/v1/countdowns", headers=headers_b).json() == []

    get_response = client.get(f"/api/v1/countdowns/{countdown_id}", headers=headers_b)
    assert get_response.status_code == 404

    update_response = client.patch(
        f"/api/v1/countdowns/{countdown_id}", json={"title": "hijacked"}, headers=headers_b
    )
    assert update_response.status_code == 404

    delete_response = client.delete(f"/api/v1/countdowns/{countdown_id}", headers=headers_b)
    assert delete_response.status_code == 404
