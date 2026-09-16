import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.countdown import DEFAULT_NOTIFICATION_OFFSETS_MINUTES

PRIORITY_PATTERN = "^(low|medium|high)$"
REPEAT_RULE_PATTERN = "^(none|daily|weekly|monthly|yearly)$"


class CountdownCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    target_datetime: datetime
    category: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=4000)
    priority: str = Field(default="medium", pattern=PRIORITY_PATTERN)
    repeat_rule: str = Field(default="none", pattern=REPEAT_RULE_PATTERN)
    notification_offsets_minutes: list[int] = Field(
        default_factory=lambda: list(DEFAULT_NOTIFICATION_OFFSETS_MINUTES)
    )


class CountdownUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    target_datetime: datetime | None = None
    category: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=4000)
    priority: str | None = Field(default=None, pattern=PRIORITY_PATTERN)
    repeat_rule: str | None = Field(default=None, pattern=REPEAT_RULE_PATTERN)
    notification_offsets_minutes: list[int] | None = None
    is_active: bool | None = None


class CountdownRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    target_datetime: datetime
    category: str | None
    notes: str | None
    priority: str
    repeat_rule: str
    notification_offsets_minutes: list[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime
