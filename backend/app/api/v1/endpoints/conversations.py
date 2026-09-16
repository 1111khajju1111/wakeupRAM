import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.ram_core import handle_user_message
from app.api.v1.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.conversation import (
    ConversationCreate,
    ConversationRead,
    MessageCreate,
    MessageExchange,
    MessageRead,
)
from app.services import conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationRead])
def list_conversations(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ConversationRead]:
    return conversation_service.list_conversations(db, current_user.id)


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationRead:
    return conversation_service.create_conversation(
        db, current_user.id, mode=payload.mode, title=payload.title
    )


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
def list_messages(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MessageRead]:
    try:
        return conversation_service.list_messages(db, current_user.id, conversation_id)
    except conversation_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{conversation_id}/messages", response_model=MessageExchange)
def send_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageExchange:
    """The main chat endpoint. Always returns 200 with a (possibly
    fallback-labeled) assistant message — an AI provider outage is a degraded
    response, not an HTTP error, since the user's message was saved either way."""
    preferred_language = current_user.profile.preferred_language if current_user.profile else "en"

    try:
        user_message, assistant_message = handle_user_message(
            db, current_user.id, conversation_id, payload.content, preferred_language
        )
    except conversation_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return MessageExchange(user_message=user_message, assistant_message=assistant_message)
