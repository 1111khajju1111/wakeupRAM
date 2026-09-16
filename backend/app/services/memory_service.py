import uuid
from datetime import datetime, timezone

from sqlalchemy import nullslast, select
from sqlalchemy.orm import Session

from app.models.memory import Memory

VALID_CATEGORIES = {
    "fact",
    "preference",
    "goal_context",
    "habit_context",
    "lesson",
    "behavior_pattern",
    "context",
}


class NotFoundError(Exception):
    pass


def store_user_stated_fact(db: Session, user_id: uuid.UUID, category: str, content: str) -> Memory:
    """For anything the user told Ram directly and explicitly — always
    confidence 1.0, source user_stated. Never called for anything the model
    guessed."""
    return _upsert(db, user_id, category, content, source="user_stated", confidence=1.0)


def store_extracted_memory(
    db: Session, user_id: uuid.UUID, category: str, content: str, confidence: float
) -> Memory:
    """For candidates the AI proposed extracting from a conversation.
    Confidence is clamped and the memory is explicitly marked non-user-stated
    so personality.py always labels it INFERRED, never KNOWN."""
    clamped_confidence = max(0.0, min(1.0, confidence))
    return _upsert(
        db, user_id, category, content, source="conversation_extracted", confidence=clamped_confidence
    )


def store_inferred_pattern(
    db: Session, user_id: uuid.UUID, content: str, confidence: float
) -> Memory:
    """For patterns a domain service (not the conversational AI) detected
    deterministically from a user's own logged data — e.g. smoking_service
    noticing the same trigger recurring. Distinct from
    store_extracted_memory (which is for candidates the AI proposed from
    conversation text): source=ai_inferred so it's traceable to "the system
    noticed this in your data" rather than "the AI inferred this from what
    you said". Always category=behavior_pattern and always surfaces to
    personality.py as INFERRED, never as a settled fact."""
    clamped_confidence = max(0.0, min(1.0, confidence))
    return _upsert(
        db, user_id, "behavior_pattern", content, source="ai_inferred", confidence=clamped_confidence
    )


def supersede_stale_variants(
    db: Session, user_id: uuid.UUID, category: str, identity_prefix: str, keep_content: str
) -> None:
    """_upsert above dedups on EXACT content match — which fails the moment a
    pattern's rendered text embeds a live number (e.g. smoking_service's
    "...3 times in the last 30 days" becoming "...4 times..." on the next
    event). Without this, every count change would insert a brand new
    active memory instead of updating the existing one, leaving a growing
    pile of near-identical rows differing only by a stale count — exactly
    the "uncontrolled archive" the master doc's memory section rules out.

    Call this with a stable prefix (independent of the count/detail that
    changes) right before store_inferred_pattern: any other active memory
    in this category that starts with the same prefix is marked
    superseded, so _upsert's exact-match lookup starts clean and inserts
    exactly one current row instead of accumulating variants. `keep_content`
    is the content about to be (re)written and is never touched here — it's
    left for _upsert to find-or-create normally."""
    candidates = db.execute(
        select(Memory).where(
            Memory.user_id == user_id,
            Memory.category == category,
            Memory.status == "active",
        )
    ).scalars()
    for memory in candidates:
        if memory.content == keep_content:
            continue
        if memory.content.startswith(identity_prefix):
            memory.status = "superseded"
            db.add(memory)
    db.commit()


def _upsert(
    db: Session, user_id: uuid.UUID, category: str, content: str, *, source: str, confidence: float
) -> Memory:
    if category not in VALID_CATEGORIES:
        category = "context"  # fail safe rather than reject the whole exchange

    # Exact-content dedup within the same category: refreshes confidence/
    # relevance/last_used_at on the existing row instead of piling up
    # near-duplicate memories every time the same fact comes up.
    existing = db.execute(
        select(Memory).where(
            Memory.user_id == user_id,
            Memory.category == category,
            Memory.content == content,
            Memory.status == "active",
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if existing:
        existing.confidence = max(existing.confidence, confidence)
        existing.last_used_at = now
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    memory = Memory(
        user_id=user_id,
        category=category,
        content=content,
        source=source,
        confidence=confidence,
        last_used_at=now,
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


def list_memories(
    db: Session, user_id: uuid.UUID, category: str | None = None, status: str = "active"
) -> list[Memory]:
    stmt = select(Memory).where(Memory.user_id == user_id, Memory.status == status)
    if category:
        stmt = stmt.where(Memory.category == category)
    return list(db.execute(stmt.order_by(Memory.relevance.desc(), Memory.updated_at.desc())).scalars())


def retrieve_for_prompt(db: Session, user_id: uuid.UUID, limit: int) -> list[Memory]:
    """Simple recency/relevance retrieval for Phase 3. Real semantic
    (embedding-based) retrieval is future ML work — this is the honest
    placeholder until then, not a claim of smarter ranking than it does."""
    stmt = (
        select(Memory)
        .where(Memory.user_id == user_id, Memory.status == "active")
        .order_by(Memory.relevance.desc(), nullslast(Memory.last_used_at.desc()))
        .limit(limit)
    )
    memories = list(db.execute(stmt).scalars())

    now = datetime.now(timezone.utc)
    for memory in memories:
        memory.last_used_at = now
        db.add(memory)
    db.commit()

    return memories


def _get_owned_memory(db: Session, user_id: uuid.UUID, memory_id: uuid.UUID) -> Memory:
    memory = db.execute(
        select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
    ).scalar_one_or_none()
    if memory is None:
        raise NotFoundError("Memory not found")
    return memory


def archive_memory(db: Session, user_id: uuid.UUID, memory_id: uuid.UUID) -> Memory:
    memory = _get_owned_memory(db, user_id, memory_id)
    memory.status = "archived"
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


def delete_memory(db: Session, user_id: uuid.UUID, memory_id: uuid.UUID) -> None:
    memory = _get_owned_memory(db, user_id, memory_id)
    db.delete(memory)
    db.commit()
