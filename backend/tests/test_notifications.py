import uuid
from datetime import datetime, timedelta, timezone

from app.services import notification_service
from tests.helpers import register_and_login


def _get_user_id(client, headers):
    return uuid.UUID(client.get("/api/v1/users/me", headers=headers).json()["id"])


def _create_countdown(client, headers, **overrides):
    payload = {
        "title": "Board exam",
        "target_datetime": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
    }
    payload.update(overrides)
    return client.post("/api/v1/countdowns", json=payload, headers=headers)


def test_preferences_have_sane_defaults(client):
    headers = register_and_login(client)

    response = client.get("/api/v1/notifications/preferences", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["max_per_day"] == 6
    assert body["quiet_hours_start_hour"] is None
    assert body["quiet_hours_end_hour"] is None
    assert all(body["enabled_types"].values())


def test_update_preferences(client):
    headers = register_and_login(client)

    response = client.patch(
        "/api/v1/notifications/preferences",
        json={"max_per_day": 3, "quiet_hours_start_hour": 22, "quiet_hours_end_hour": 7},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["max_per_day"] == 3
    assert body["quiet_hours_start_hour"] == 22
    assert body["quiet_hours_end_hour"] == 7


def test_disabling_a_type_is_rejected_for_unknown_keys(client):
    headers = register_and_login(client)

    response = client.patch(
        "/api/v1/notifications/preferences", json={"enabled_types": {"not_a_real_type": False}}, headers=headers
    )
    assert response.status_code == 422


def test_no_notifications_exist_until_something_triggers_them(client):
    headers = register_and_login(client)

    assert client.get("/api/v1/notifications", headers=headers).json() == []


def test_refresh_generates_a_deadline_notification_once_offset_threshold_reached(client):
    headers = register_and_login(client)
    # Target 30 minutes away with a 60-minute offset: the threshold
    # (target - 60min) is already in the past, so this should fire now.
    target = datetime.now(timezone.utc) + timedelta(minutes=30)
    _create_countdown(
        client, headers, title="Submission deadline", target_datetime=target.isoformat(),
        notification_offsets_minutes=[60],
    )

    response = client.post("/api/v1/notifications/refresh", headers=headers)
    assert response.status_code == 200
    created = response.json()
    assert len(created) == 1
    assert created[0]["type"] == "deadline"
    assert "Submission deadline" in created[0]["body"]
    assert created[0]["status"] == "pending"


def test_refresh_does_not_fire_before_the_offset_threshold(client):
    headers = register_and_login(client)
    # Target 3 days away with only a 60-minute offset: nowhere near due.
    target = datetime.now(timezone.utc) + timedelta(days=3)
    _create_countdown(
        client, headers, target_datetime=target.isoformat(), notification_offsets_minutes=[60]
    )

    response = client.post("/api/v1/notifications/refresh", headers=headers)
    assert response.json() == []


def test_refresh_is_idempotent_thanks_to_dedupe_key(client):
    headers = register_and_login(client)
    target = datetime.now(timezone.utc) + timedelta(minutes=10)
    _create_countdown(client, headers, target_datetime=target.isoformat(), notification_offsets_minutes=[60])

    first = client.post("/api/v1/notifications/refresh", headers=headers).json()
    second = client.post("/api/v1/notifications/refresh", headers=headers).json()

    assert len(first) == 1
    assert second == []  # already generated — no duplicate
    assert len(client.get("/api/v1/notifications", headers=headers).json()) == 1


def test_disabled_type_never_generates_notifications(client):
    headers = register_and_login(client)
    client.patch(
        "/api/v1/notifications/preferences", json={"enabled_types": {"deadline": False}}, headers=headers
    )
    target = datetime.now(timezone.utc) + timedelta(minutes=10)
    _create_countdown(client, headers, target_datetime=target.isoformat(), notification_offsets_minutes=[60])

    response = client.post("/api/v1/notifications/refresh", headers=headers)
    assert response.json() == []


def test_daily_cap_limits_how_many_notifications_are_created(client):
    headers = register_and_login(client)
    client.patch("/api/v1/notifications/preferences", json={"max_per_day": 1}, headers=headers)

    target = datetime.now(timezone.utc) + timedelta(minutes=10)
    for i in range(3):
        _create_countdown(
            client, headers, title=f"Deadline {i}", target_datetime=target.isoformat(),
            notification_offsets_minutes=[60],
        )

    created = client.post("/api/v1/notifications/refresh", headers=headers).json()
    assert len(created) == 1


def test_dismiss_is_a_final_state(client):
    headers = register_and_login(client)
    target = datetime.now(timezone.utc) + timedelta(minutes=10)
    _create_countdown(client, headers, target_datetime=target.isoformat(), notification_offsets_minutes=[60])
    notification_id = client.post("/api/v1/notifications/refresh", headers=headers).json()[0]["id"]

    dismiss = client.patch(
        f"/api/v1/notifications/{notification_id}", json={"status": "dismissed"}, headers=headers
    )
    assert dismiss.status_code == 200

    second_attempt = client.patch(
        f"/api/v1/notifications/{notification_id}", json={"status": "actioned"}, headers=headers
    )
    assert second_attempt.status_code == 409


def test_habit_intervention_fires_only_past_the_risk_hour(client, db_session):
    headers = register_and_login(client)
    user_id = _get_user_id(client, headers)
    client.post("/api/v1/habits", json={"title": "Evening reading", "frequency": "daily"}, headers=headers)

    morning = datetime.now(timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0)
    evening = datetime.now(timezone.utc).replace(hour=20, minute=0, second=0, microsecond=0)

    assert notification_service.generate_for_user(db_session, user_id, now=morning) == []
    created = notification_service.generate_for_user(db_session, user_id, now=evening)
    assert len(created) == 1
    assert created[0].type == "habit_intervention"


def test_habit_intervention_does_not_fire_once_logged(client, db_session):
    headers = register_and_login(client)
    user_id = _get_user_id(client, headers)
    habit_id = client.post(
        "/api/v1/habits", json={"title": "Evening reading", "frequency": "daily"}, headers=headers
    ).json()["id"]
    client.post(f"/api/v1/habits/{habit_id}/logs", json={}, headers=headers)

    evening = datetime.now(timezone.utc).replace(hour=20, minute=0, second=0, microsecond=0)
    assert notification_service.generate_for_user(db_session, user_id, now=evening) == []


def test_quiet_hours_defers_trigger_time_rather_than_dropping_it(client, db_session):
    headers = register_and_login(client)
    user_id = _get_user_id(client, headers)
    client.patch(
        "/api/v1/notifications/preferences",
        json={"quiet_hours_start_hour": 22, "quiet_hours_end_hour": 7},
        headers=headers,
    )

    late_night = datetime.now(timezone.utc).replace(hour=23, minute=0, second=0, microsecond=0)
    target = late_night + timedelta(minutes=10)
    _create_countdown(client, headers, target_datetime=target.isoformat(), notification_offsets_minutes=[60])

    created = notification_service.generate_for_user(db_session, user_id, now=late_night)
    assert len(created) == 1
    assert created[0].trigger_at.hour == 7  # deferred to quiet_hours_end, not delivered at 23:00


def test_user_cannot_access_another_users_notifications(client):
    headers_a = register_and_login(client, email="a@example.com")
    headers_b = register_and_login(client, email="b@example.com")

    target = datetime.now(timezone.utc) + timedelta(minutes=10)
    _create_countdown(client, headers_a, target_datetime=target.isoformat(), notification_offsets_minutes=[60])
    notification_id = client.post("/api/v1/notifications/refresh", headers=headers_a).json()[0]["id"]

    assert client.get("/api/v1/notifications", headers=headers_b).json() == []

    response = client.patch(
        f"/api/v1/notifications/{notification_id}", json={"status": "dismissed"}, headers=headers_b
    )
    assert response.status_code == 404
