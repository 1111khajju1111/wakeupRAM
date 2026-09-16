import uuid

from app.ai.personality import build_memory_context
from app.services import memory_service
from tests.helpers import register_and_login


def _get_user_id(client, headers):
    return uuid.UUID(client.get("/api/v1/users/me", headers=headers).json()["id"])


def test_user_stated_fact_is_full_confidence(client, db_session):
    headers = register_and_login(client)
    user_id = _get_user_id(client, headers)

    memory = memory_service.store_user_stated_fact(db_session, user_id, "fact", "Lives in Machilipatnam")
    assert memory.confidence == 1.0
    assert memory.source == "user_stated"


def test_extracted_memory_is_never_full_confidence_by_default(client, db_session):
    headers = register_and_login(client)
    user_id = _get_user_id(client, headers)

    memory = memory_service.store_extracted_memory(
        db_session, user_id, "behavior_pattern", "Skips workouts after poor sleep", confidence=0.6
    )
    assert memory.source == "conversation_extracted"
    assert memory.confidence == 0.6


def test_duplicate_content_dedups_instead_of_creating_new_row(client, db_session):
    headers = register_and_login(client)
    user_id = _get_user_id(client, headers)

    memory_service.store_extracted_memory(db_session, user_id, "fact", "Prefers Telugu", confidence=0.5)
    memory_service.store_extracted_memory(db_session, user_id, "fact", "Prefers Telugu", confidence=0.8)

    memories = memory_service.list_memories(db_session, user_id, category="fact")
    assert len(memories) == 1
    assert memories[0].confidence == 0.8  # took the higher confidence, didn't duplicate


def test_memory_context_labels_known_vs_inferred(client, db_session):
    headers = register_and_login(client)
    user_id = _get_user_id(client, headers)

    memory_service.store_user_stated_fact(db_session, user_id, "fact", "Is a BTech student")
    memory_service.store_extracted_memory(
        db_session, user_id, "behavior_pattern", "May study better at night", confidence=0.4
    )

    memories = memory_service.list_memories(db_session, user_id)
    context = build_memory_context(memories)

    assert "Is a BTech student" in context and "KNOWN" in context
    assert "May study better at night" in context and "INFERRED" in context


def test_user_can_archive_and_delete_own_memory(client, db_session):
    headers = register_and_login(client)
    user_id = _get_user_id(client, headers)
    memory = memory_service.store_user_stated_fact(db_session, user_id, "preference", "Prefers dark theme")

    archived = memory_service.archive_memory(db_session, user_id, memory.id)
    assert archived.status == "archived"

    memory_service.delete_memory(db_session, user_id, memory.id)
    remaining = memory_service.list_memories(db_session, user_id, status="archived")
    assert remaining == []


def test_api_lists_memories_for_current_user_only(client, db_session):
    headers_a = register_and_login(client, email="a@example.com")
    headers_b = register_and_login(client, email="b@example.com")
    user_id_a = _get_user_id(client, headers_a)

    memory_service.store_user_stated_fact(db_session, user_id_a, "fact", "A's private fact")

    memories_a = client.get("/api/v1/memories", headers=headers_a).json()
    memories_b = client.get("/api/v1/memories", headers=headers_b).json()

    assert len(memories_a) == 1
    assert memories_b == []
