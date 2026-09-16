import uuid
from datetime import datetime, timedelta, timezone

from app.services import memory_service
from tests.helpers import register_and_login


def _get_user_id(client, headers):
    return uuid.UUID(client.get("/api/v1/users/me", headers=headers).json()["id"])


def _log_event(client, headers, *, trigger="stress", intensity=6, outcome="resisted", occurred_at=None):
    payload = {
        "trigger": trigger,
        "craving_intensity": intensity,
        "outcome": outcome,
    }
    if occurred_at is not None:
        payload["occurred_at"] = occurred_at.isoformat()
    return client.post("/api/v1/smoking/events", json=payload, headers=headers)


def test_create_event_and_list(client):
    headers = register_and_login(client)

    response = _log_event(client, headers, trigger="after lunch", intensity=7, outcome="resisted")
    assert response.status_code == 201
    assert response.json()["trigger"] == "after lunch"
    assert response.json()["outcome"] == "resisted"

    events = client.get("/api/v1/smoking/events", headers=headers).json()
    assert len(events) == 1


def test_invalid_outcome_is_rejected(client):
    headers = register_and_login(client)

    response = client.post(
        "/api/v1/smoking/events",
        json={"trigger": "boredom", "craving_intensity": 5, "outcome": "gave_up"},
        headers=headers,
    )
    assert response.status_code == 422


def test_intensity_out_of_range_is_rejected(client):
    headers = register_and_login(client)

    response = client.post(
        "/api/v1/smoking/events",
        json={"trigger": "boredom", "craving_intensity": 11, "outcome": "resisted"},
        headers=headers,
    )
    assert response.status_code == 422


def test_a_smoked_outcome_is_recorded_the_same_way_as_any_other(client):
    """No shaming, no special validation, no different status code for a
    slip — section 10's no-shame requirement means "smoked" is just another
    valid outcome value, recorded neutrally."""
    headers = register_and_login(client)

    response = _log_event(client, headers, trigger="argument", intensity=8, outcome="smoked")
    assert response.status_code == 201
    assert response.json()["outcome"] == "smoked"


def test_reflection_note_can_be_added_after_the_fact(client):
    headers = register_and_login(client)
    event_id = _log_event(client, headers, outcome="smoked").json()["id"]

    response = client.patch(
        f"/api/v1/smoking/events/{event_id}",
        json={"reflection_note": "Controllable: leaving the room during the argument. Learned: step outside for air instead."},
        headers=headers,
    )
    assert response.status_code == 200
    assert "Controllable" in response.json()["reflection_note"]


def test_summary_counts_outcomes_in_window(client):
    headers = register_and_login(client)

    _log_event(client, headers, outcome="resisted")
    _log_event(client, headers, outcome="resisted")
    _log_event(client, headers, outcome="alternative_used")
    _log_event(client, headers, outcome="smoked")

    summary = client.get("/api/v1/smoking/summary", headers=headers).json()
    assert summary["total_events"] == 4
    assert summary["resisted_count"] == 2
    assert summary["alternative_used_count"] == 1
    assert summary["smoked_count"] == 1


def test_smoke_free_streak_is_none_when_nothing_logged(client):
    headers = register_and_login(client)

    summary = client.get("/api/v1/smoking/summary", headers=headers).json()
    assert summary["smoke_free_streak_days"] is None
    assert summary["last_event"] is None


def test_smoke_free_streak_measured_from_last_smoked_event(client):
    headers = register_and_login(client)
    ten_days_ago = datetime.now(timezone.utc) - timedelta(days=10)

    _log_event(client, headers, outcome="smoked", occurred_at=ten_days_ago)
    _log_event(client, headers, outcome="resisted")  # today, doesn't reset the "since last smoked" clock

    summary = client.get("/api/v1/smoking/summary", headers=headers).json()
    assert summary["smoke_free_streak_days"] == 10


def test_pattern_not_detected_below_threshold(client):
    headers = register_and_login(client)

    _log_event(client, headers, trigger="stress", outcome="smoked")
    _log_event(client, headers, trigger="stress", outcome="smoked")  # only 2 — below the threshold of 3

    summary = client.get("/api/v1/smoking/summary", headers=headers).json()
    assert summary["detected_patterns"] == []


def test_pattern_detected_at_threshold_and_written_to_memory(client, db_session):
    headers = register_and_login(client)
    user_id = _get_user_id(client, headers)

    for _ in range(3):
        _log_event(client, headers, trigger="After coffee", outcome="smoked")

    summary = client.get("/api/v1/smoking/summary", headers=headers).json()
    trigger_patterns = [p for p in summary["detected_patterns"] if p["pattern_type"] == "trigger"]
    assert len(trigger_patterns) == 1
    assert trigger_patterns[0]["occurrences"] == 3
    assert "after coffee" in trigger_patterns[0]["description"].lower()

    # The same detection also lands in Memory as INFERRED, never a settled
    # fact, so it surfaces in the next RAM Core conversation automatically.
    patterns_in_memory = memory_service.list_memories(db_session, user_id, category="behavior_pattern")
    assert len(patterns_in_memory) >= 1
    assert patterns_in_memory[0].source == "ai_inferred"
    assert patterns_in_memory[0].confidence < 1.0


def test_a_growing_pattern_updates_memory_instead_of_piling_up_duplicates(client, db_session):
    """The rendered pattern description embeds a live count ("...3 times",
    then "...4 times"). Without superseding the old variant, the exact-
    content dedup in memory_service would never match and each new event
    past the threshold would insert a fresh near-duplicate memory."""
    headers = register_and_login(client)
    user_id = _get_user_id(client, headers)

    for _ in range(3):
        _log_event(client, headers, trigger="After coffee", outcome="smoked")

    # A 4th matching event bumps the count from 3 to 4 in the description.
    _log_event(client, headers, trigger="After coffee", outcome="smoked")

    active_patterns = memory_service.list_memories(db_session, user_id, category="behavior_pattern")
    # Filter to the plain trigger pattern specifically (identity prefix
    # 'Smoking has followed the trigger "..."'), not the separate
    # trigger+time-of-day combo pattern that also legitimately mentions
    # "after coffee" in its own text — that's a different, correctly
    # co-existing pattern, not a duplicate of this one.
    trigger_variants = [
        m for m in active_patterns if m.content.lower().startswith('smoking has followed the trigger "after coffee"')
    ]
    assert len(trigger_variants) == 1
    assert "4 times" in trigger_variants[0].content

    # No pattern of any type should have a stale "3 times" variant sitting
    # alongside the current "4 times" one — that's the actual pile-up bug
    # this test guards against.
    assert not any("3 times" in m.content for m in active_patterns)


def test_resisted_and_alternative_events_never_count_toward_a_pattern(client):
    """Patterns are about the thing the system should intervene on — a
    recurring lead-up to actually smoking — not about resisting well, which
    would be a strange thing to flag as a "risk pattern"."""
    headers = register_and_login(client)

    for _ in range(3):
        _log_event(client, headers, trigger="after dinner", outcome="resisted")

    summary = client.get("/api/v1/smoking/summary", headers=headers).json()
    assert summary["detected_patterns"] == []


def test_user_cannot_access_another_users_smoking_events(client):
    headers_a = register_and_login(client, email="a@example.com")
    headers_b = register_and_login(client, email="b@example.com")

    event_id = _log_event(client, headers_a, trigger="A's private trigger").json()["id"]

    events_b = client.get("/api/v1/smoking/events", headers=headers_b).json()
    assert events_b == []

    update_response = client.patch(
        f"/api/v1/smoking/events/{event_id}", json={"notes": "trying to edit someone else's log"}, headers=headers_b
    )
    assert update_response.status_code == 404

    delete_response = client.delete(f"/api/v1/smoking/events/{event_id}", headers=headers_b)
    assert delete_response.status_code == 404

    summary_b = client.get("/api/v1/smoking/summary", headers=headers_b).json()
    assert summary_b["total_events"] == 0
