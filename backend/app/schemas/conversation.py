import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    mode: str = Field(
        default="adaptive",
        pattern="^(friend|teacher|commander|coach|financial_guide|health_coach|adaptive)$",
    )


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    mode: str
    last_message_at: datetime | None
    created_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    is_fallback: bool
    created_at: datetime


class MessageExchange(BaseModel):
    user_message: MessageRead
    assistant_message: MessageRead
