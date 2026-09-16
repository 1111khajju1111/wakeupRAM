import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

OUTCOME_PATTERN = "^(resisted|alternative_used|smoked)$"


class SmokingEventCreate(BaseModel):
    trigger: str = Field(min_length=1, max_length=200)
    craving_intensity: int = Field(ge=1, le=10)
    stress_level: int | None = Field(default=None, ge=1, le=5)
    context: str | None = Field(default=None, max_length=500)
    outcome: str = Field(pattern=OUTCOME_PATTERN)
    alternative_action: str | None = Field(default=None, max_length=300)
    reflection_note: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=1000)
    occurred_at: datetime | None = None  # defaults to now (server-side) if omitted


class SmokingEventUpdate(BaseModel):
    """Deliberately narrow: an event's trigger/intensity/outcome describe what
    already happened and shouldn't be rewritten after the fact. What's
    editable is adding a reflection afterward — the no-shame, understand-and-
    learn step from section 5 — plus free-text notes."""

    reflection_note: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=1000)


class SmokingEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trigger: str
    craving_intensity: int
    stress_level: int | None
    context: str | None
    outcome: str
    alternative_action: str | None
    reflection_note: str | None
    notes: str | None
    occurred_at: datetime


class DetectedPattern(BaseModel):
    """A deterministic, frequency-based observation — not an ML prediction
    (that's Phase 10). Always exposes the evidence (occurrences, window) it's
    based on rather than asserting confidence it doesn't have."""

    pattern_type: str  # trigger | time_of_day | trigger_and_time_of_day
    description: str
    occurrences: int
    window_days: int


class SmokingSummary(BaseModel):
    window_days: int
    total_events: int
    smoked_count: int
    resisted_count: int
    alternative_used_count: int
    # None (not 0) when no event has ever been logged — an honest "unknown",
    # same convention as HealthTodaySummary.calories_total.
    smoke_free_streak_days: int | None
    last_event: SmokingEventRead | None
    detected_patterns: list[DetectedPattern]
