import uuid
from datetime import datetime, timezone

from sqlalchemy import nullslast, select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, Message


class NotFoundError(Exception):
    pass


def create_conversation(
    db: Session, user_id: uuid.UUID, mode: str, title: str | None = None, language_override: str | None = None
) -> Conversation:
    conversation = Conversation(user_id=user_id, mode=mode, title=title, language_override=language_override)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def list_conversations(db: Session, user_id: uuid.UUID) -> list[Conversation]:
    stmt = select(Conversation).where(Conversation.user_id == user_id).order_by(
        nullslast(Conversation.last_message_at.desc()), Conversation.created_at.desc()
    )
    return list(db.execute(stmt).scalars())


def get_owned_conversation(db: Session, user_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation:
    conversation = db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    ).scalar_one_or_none()
    if conversation is None:
        raise NotFoundError("Conversation not found")
    return conversation


def list_messages(db: Session, user_id: uuid.UUID, conversation_id: uuid.UUID, limit: int = 50) -> list[Message]:
    # Confirms ownership before returning anything — a valid message ID under
    # a conversation owned by someone else must never be reachable this way.
    get_owned_conversation(db, user_id, conversation_id)

    # Fetch the most recent `limit` messages (DESC + limit), then reverse to
    # chronological order. Ordering ASC-then-LIMIT would silently return the
    # OLDEST messages once a conversation passes `limit` in length — which
    # means the just-sent message (and all recent context) would drop out of
    # what RAM Core sends to the AI provider forever. DESC-then-reverse is
    # what actually keeps "most recent N, in order."
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = list(db.execute(stmt).scalars())
    messages.reverse()
    return messages


def append_message(
    db: Session,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    is_fallback: bool = False,
) -> Message:
    conversation = get_owned_conversation(db, user_id, conversation_id)

    message = Message(
        conversation_id=conversation_id,
        user_id=user_id,
        role=role,
        content=content,
        is_fallback=is_fallback,
    )
    db.add(message)

    conversation.last_message_at = datetime.now(timezone.utc)
    db.add(conversation)

    db.commit()
    db.refresh(message)
    return message
