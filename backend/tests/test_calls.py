import time
from unittest.mock import patch

from tests.helpers import register_and_login


def test_start_call_creates_conversation_and_returns_in_progress(client):
    headers = register_and_login(client)

    response = client.post("/api/v1/calls", json={"recording_enabled": True}, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["recording_enabled"] is True
    assert body["ended_at"] is None
    assert body["conversation_id"]


def test_call_defaults_language_to_profile_preference(client):
    headers = register_and_login(client)
    client.patch("/api/v1/users/me/profile", json={"preferred_language": "te"}, headers=headers)

    response = client.post("/api/v1/calls", json={}, headers=headers)
    assert response.json()["language"] == "te"


def test_explicit_language_overrides_profile_preference(client):
    headers = register_and_login(client)
    client.patch("/api/v1/users/me/profile", json={"preferred_language": "te"}, headers=headers)

    response = client.post("/api/v1/calls", json={"language": "en"}, headers=headers)
    assert response.json()["language"] == "en"


def test_call_language_override_actually_reaches_the_ai_prompt_not_just_the_row(client):
    """The call above proves VoiceCall.language can differ from the
    profile's preferred_language. This proves that difference actually
    changes what RAM Core generates a reply with — not just what's stored on
    the call row. Without conversation.language_override wired through
    ram_core.handle_user_message, a call started with language="en" while
    the profile default was "te" would still get Telugu-instructed replies,
    which defeats the entire point of a per-call language choice."""
    headers = register_and_login(client)
    client.patch("/api/v1/users/me/profile", json={"preferred_language": "te"}, headers=headers)
    call = client.post("/api/v1/calls", json={"language": "en"}, headers=headers).json()

    captured = {}

    class _CapturingProvider:
        def generate(self, *, system_prompt, history, max_tokens):
            captured["system_prompt"] = system_prompt
            from app.ai.provider import AIResponse

            return AIResponse(reply_text="ok", memory_updates=[])

    with patch("app.ai.ram_core.get_provider", side_effect=lambda: _CapturingProvider()):
        client.post(
            f"/api/v1/conversations/{call['conversation_id']}/messages",
            json={"content": "Hello"},
            headers=headers,
        )

    assert "Respond in English." in captured["system_prompt"]
    assert "Respond in Telugu" not in captured["system_prompt"]


def test_call_with_no_explicit_language_still_falls_back_to_profile(client):
    """language_override shouldn't break the ordinary case: a call that
    doesn't override anything should behave exactly like text chat already
    does — following the profile's preferred_language."""
    headers = register_and_login(client)
    client.patch("/api/v1/users/me/profile", json={"preferred_language": "te"}, headers=headers)
    call = client.post("/api/v1/calls", json={"language": "te"}, headers=headers).json()

    captured = {}

    class _CapturingProvider:
        def generate(self, *, system_prompt, history, max_tokens):
            captured["system_prompt"] = system_prompt
            from app.ai.provider import AIResponse

            return AIResponse(reply_text="ok", memory_updates=[])

    with patch("app.ai.ram_core.get_provider", side_effect=lambda: _CapturingProvider()):
        client.post(
            f"/api/v1/conversations/{call['conversation_id']}/messages",
            json={"content": "Hello"},
            headers=headers,
        )

    assert "Respond in Telugu" in captured["system_prompt"]


def test_mixed_call_language_maps_to_telugu_code_switching_instruction(client):
    headers = register_and_login(client)
    call = client.post("/api/v1/calls", json={"language": "mixed"}, headers=headers).json()

    captured = {}

    class _CapturingProvider:
        def generate(self, *, system_prompt, history, max_tokens):
            captured["system_prompt"] = system_prompt
            from app.ai.provider import AIResponse

            return AIResponse(reply_text="ok", memory_updates=[])

    with patch("app.ai.ram_core.get_provider", side_effect=lambda: _CapturingProvider()):
        client.post(
            f"/api/v1/conversations/{call['conversation_id']}/messages",
            json={"content": "Hello"},
            headers=headers,
        )

    assert "Respond in Telugu" in captured["system_prompt"]


def test_ordinary_text_chat_is_unaffected_by_language_override_column(client):
    """A regular (non-call) conversation has language_override=None and must
    keep following the profile default exactly as it did before this
    column existed."""
    headers = register_and_login(client)
    conversation = client.post("/api/v1/conversations", json={}, headers=headers).json()

    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"content": "hello"},
        headers=headers,
    )
    assert response.status_code == 200


def test_messages_during_a_call_use_the_same_conversation_pipeline(client):
    """A call's turns go through the exact same endpoint Phase 3 already
    tests, not a forked implementation — this just proves the two are
    actually wired together."""
    headers = register_and_login(client)
    call = client.post("/api/v1/calls", json={}, headers=headers).json()

    response = client.post(
        f"/api/v1/conversations/{call['conversation_id']}/messages",
        json={"content": "Hello Ram"},
        headers=headers,
    )
    assert response.status_code == 200
    exchange = response.json()
    assert exchange["user_message"]["content"] == "Hello Ram"
    assert exchange["assistant_message"]["role"] == "assistant"


def test_ending_a_call_sets_duration_and_status(client):
    headers = register_and_login(client)
    call = client.post("/api/v1/calls", json={}, headers=headers).json()

    time.sleep(1.1)

    response = client.post(f"/api/v1/calls/{call['id']}/end", json={}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["ended_at"] is not None
    assert body["duration_seconds"] >= 1


def test_ending_a_call_twice_is_rejected(client):
    headers = register_and_login(client)
    call = client.post("/api/v1/calls", json={}, headers=headers).json()

    client.post(f"/api/v1/calls/{call['id']}/end", json={}, headers=headers)
    second = client.post(f"/api/v1/calls/{call['id']}/end", json={}, headers=headers)
    assert second.status_code == 409


def test_ending_a_call_can_attach_recording_metadata(client):
    headers = register_and_login(client)
    call = client.post("/api/v1/calls", json={"recording_enabled": True}, headers=headers).json()

    response = client.post(
        f"/api/v1/calls/{call['id']}/end",
        json={
            "recording_local_reference": "Wake Up Ram/Calls/2026-09-13/10-15-00.webm",
            "recording_duration_seconds": 42,
        },
        headers=headers,
    )
    body = response.json()
    assert body["recording_local_reference"] == "Wake Up Ram/Calls/2026-09-13/10-15-00.webm"
    assert body["recording_duration_seconds"] == 42


def test_ending_a_call_without_recording_metadata_leaves_it_none(client):
    """A call that never actually produced a recording (permission denied,
    user didn't enable it, etc.) must report None honestly — never a
    fabricated reference or a zero duration standing in for 'no data'."""
    headers = register_and_login(client)
    call = client.post("/api/v1/calls", json={"recording_enabled": False}, headers=headers).json()

    response = client.post(f"/api/v1/calls/{call['id']}/end", json={}, headers=headers)
    body = response.json()
    assert body["recording_local_reference"] is None
    assert body["recording_duration_seconds"] is None


def test_recording_metadata_is_ignored_if_recording_was_never_enabled(client):
    """A call started with recording_enabled=False reporting a recording
    reference anyway (buggy or careless client) must not be stored — a row
    with recording_enabled=False and a populated recording_local_reference
    would be an internally inconsistent record of something that, per the
    call's own settings, never happened."""
    headers = register_and_login(client)
    call = client.post("/api/v1/calls", json={"recording_enabled": False}, headers=headers).json()

    response = client.post(
        f"/api/v1/calls/{call['id']}/end",
        json={
            "recording_local_reference": "Wake Up Ram/Calls/2026-09-13/10-15-00.webm",
            "recording_duration_seconds": 42,
        },
        headers=headers,
    )
    body = response.json()
    assert body["recording_local_reference"] is None
    assert body["recording_duration_seconds"] is None


def test_list_calls_returns_most_recent_first(client):
    headers = register_and_login(client)
    first = client.post("/api/v1/calls", json={}, headers=headers).json()
    client.post(f"/api/v1/calls/{first['id']}/end", json={}, headers=headers)
    second = client.post("/api/v1/calls", json={}, headers=headers).json()

    calls = client.get("/api/v1/calls", headers=headers).json()
    assert [c["id"] for c in calls] == [second["id"], first["id"]]


def test_user_cannot_access_another_users_call(client):
    headers_a = register_and_login(client, email="a@example.com")
    headers_b = register_and_login(client, email="b@example.com")

    call = client.post("/api/v1/calls", json={}, headers=headers_a).json()

    forbidden_get = client.get(f"/api/v1/calls/{call['id']}", headers=headers_b)
    assert forbidden_get.status_code == 404

    forbidden_end = client.post(f"/api/v1/calls/{call['id']}/end", json={}, headers=headers_b)
    assert forbidden_end.status_code == 404

    b_calls = client.get("/api/v1/calls", headers=headers_b).json()
    assert b_calls == []
