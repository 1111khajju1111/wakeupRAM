from unittest.mock import patch

from app.ai.provider import AIProviderUnavailable
from tests.helpers import register_and_login


def test_create_conversation_and_send_message(client):
    headers = register_and_login(client)

    conversation = client.post("/api/v1/conversations", json={"mode": "commander"}, headers=headers).json()
    assert conversation["mode"] == "commander"

    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"content": "I skipped my workout today."},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user_message"]["content"] == "I skipped my workout today."
    assert body["user_message"]["role"] == "user"
    assert body["assistant_message"]["role"] == "assistant"
    assert body["assistant_message"]["is_fallback"] is False


def test_message_history_persists_and_is_ordered(client):
    headers = register_and_login(client)
    conversation = client.post("/api/v1/conversations", json={}, headers=headers).json()

    client.post(
        f"/api/v1/conversations/{conversation['id']}/messages", json={"content": "first"}, headers=headers
    )
    client.post(
        f"/api/v1/conversations/{conversation['id']}/messages", json={"content": "second"}, headers=headers
    )

    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages", headers=headers).json()
    user_messages = [m["content"] for m in messages if m["role"] == "user"]
    assert user_messages == ["first", "second"]


def test_provider_outage_returns_labeled_fallback_not_an_error(client):
    headers = register_and_login(client)
    conversation = client.post("/api/v1/conversations", json={}, headers=headers).json()

    with patch(
        "app.ai.ram_core.get_provider",
        side_effect=lambda: _RaisingProvider(),
    ):
        response = client.post(
            f"/api/v1/conversations/{conversation['id']}/messages",
            json={"content": "hello"},
            headers=headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["assistant_message"]["is_fallback"] is True
    # the user's message must still be saved even though generation failed
    assert body["user_message"]["content"] == "hello"


class _RaisingProvider:
    def generate(self, **kwargs):
        raise AIProviderUnavailable("simulated outage")


def test_user_cannot_access_another_users_conversation(client):
    headers_a = register_and_login(client, email="a@example.com")
    headers_b = register_and_login(client, email="b@example.com")

    conversation = client.post("/api/v1/conversations", json={}, headers=headers_a).json()

    response = client.get(f"/api/v1/conversations/{conversation['id']}/messages", headers=headers_b)
    assert response.status_code == 404

    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages", json={"content": "hi"}, headers=headers_b
    )
    assert response.status_code == 404
