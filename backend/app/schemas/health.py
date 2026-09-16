import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

MEAL_TYPE_PATTERN = "^(breakfast|lunch|dinner|snack)$"
INTENSITY_PATTERN = "^(low|medium|high)$"
MOOD_PATTERN = "^(very_low|low|neutral|good|great)$"


# ---- Diet ----


class DietLogCreate(BaseModel):
    meal_type: str = Field(pattern=MEAL_TYPE_PATTERN)
    description: str = Field(min_length=1, max_length=500)
    calories: int | None = Field(default=None, ge=0, le=20000)
    protein_grams: float | None = Field(default=None, ge=0, le=1000)
    logged_at: datetime | None = None  # defaults to now (server-side) if omitted
    notes: str | None = Field(default=None, max_length=1000)


class DietLogUpdate(BaseModel):
    meal_type: str | None = Field(default=None, pattern=MEAL_TYPE_PATTERN)
    description: str | None = Field(default=None, min_length=1, max_length=500)
    calories: int | None = Field(default=None, ge=0, le=20000)
    protein_grams: float | None = Field(default=None, ge=0, le=1000)
    logged_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)


class DietLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meal_type: str
    description: str
    calories: int | None
    protein_grams: float | None
    logged_at: datetime
    notes: str | None


# ---- Water ----


class WaterLogCreate(BaseModel):
    amount_ml: int = Field(gt=0, le=5000)
    logged_at: datetime | None = None


class WaterLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount_ml: int
    logged_at: datetime


# ---- Sleep ----


class SleepLogCreate(BaseModel):
    sleep_date: date  # the morning this sleep session is attributed to
    bedtime: datetime | None = None
    wake_time: datetime | None = None
    # Only needed if bedtime/wake_time aren't both given — see health_service.log_sleep.
    duration_minutes: int | None = Field(default=None, ge=0, le=1440)
    quality: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = Field(default=None, max_length=1000)


class SleepLogUpdate(BaseModel):
    bedtime: datetime | None = None
    wake_time: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=0, le=1440)
    quality: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = Field(default=None, max_length=1000)


class SleepLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sleep_date: date
    bedtime: datetime | None
    wake_time: datetime | None
    duration_minutes: int | None
    quality: int | None
    notes: str | None


# ---- Workout ----


class WorkoutLogCreate(BaseModel):
    activity_type: str = Field(min_length=1, max_length=80)
    duration_minutes: int = Field(gt=0, le=1440)
    intensity: str = Field(default="medium", pattern=INTENSITY_PATTERN)
    logged_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)


class WorkoutLogUpdate(BaseModel):
    activity_type: str | None = Field(default=None, min_length=1, max_length=80)
    duration_minutes: int | None = Field(default=None, gt=0, le=1440)
    intensity: str | None = Field(default=None, pattern=INTENSITY_PATTERN)
    logged_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)


class WorkoutLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    activity_type: str
    duration_minutes: int
    intensity: str
    logged_at: datetime
    notes: str | None


# ---- Mood ----


class MoodLogCreate(BaseModel):
    mood: str = Field(pattern=MOOD_PATTERN)
    stress_level: int | None = Field(default=None, ge=1, le=5)
    journal_entry: str | None = Field(default=None, max_length=4000)
    logged_at: datetime | None = None


class MoodLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mood: str
    stress_level: int | None
    journal_entry: str | None
    logged_at: datetime


# ---- Today summary ----


class HealthTodaySummary(BaseModel):
    water_ml_total: int
    meals_logged: list[DietLogRead]
    # None (not 0) when no meal logged calories today at all — an honest
    # "unknown" rather than a fabricated zero, per the no-fake-data rule.
    calories_total: int | None
    last_night_sleep: SleepLogRead | None
    workouts_today: list[WorkoutLogRead]
    latest_mood_today: MoodLogRead | None
