import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    goal_id: uuid.UUID | None = None
    due_date: date | None = None
    priority: str = Field(default="medium", pattern="^(low|medium|high)$")
    is_daily_mission: bool = False


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    goal_id: uuid.UUID | None = None
    due_date: date | None = None
    priority: str | None = Field(default=None, pattern="^(low|medium|high)$")
    status: str | None = Field(default=None, pattern="^(pending|completed|skipped)$")
    is_daily_mission: bool | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    goal_id: uuid.UUID | None
    title: str
    description: str | None
    due_date: date | None
    priority: str
    status: str
    is_daily_mission: bool
    created_at: datetime
    updated_at: datetime


class TaskLogCreate(BaseModel):
    action: str = Field(pattern="^(completed|skipped|rescheduled)$")
    notes: str | None = Field(default=None, max_length=1000)


class TaskLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    action: str
    notes: str | None
    logged_at: datetime
