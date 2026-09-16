import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class HabitCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    frequency: str = Field(default="daily", pattern="^(daily|weekly)$")
    repeat_days: list[int] | None = None  # 0=Sun..6=Sat, required/used when frequency == weekly
    target_count_per_period: int = Field(default=1, ge=1, le=20)


class HabitUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    frequency: str | None = Field(default=None, pattern="^(daily|weekly)$")
    repeat_days: list[int] | None = None
    target_count_per_period: int | None = Field(default=None, ge=1, le=20)
    active: bool | None = None


class HabitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    frequency: str
    repeat_days: list[int] | None
    target_count_per_period: int
    active: bool
    created_at: datetime
    updated_at: datetime


class HabitLogCreate(BaseModel):
    completed_on: date | None = None  # defaults to today (server-side) if omitted
    notes: str | None = Field(default=None, max_length=500)


class HabitLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    habit_id: uuid.UUID
    completed_on: date
    notes: str | None
    logged_at: datetime


class HabitWithStreak(HabitRead):
    current_streak: int
    completed_today: bool
