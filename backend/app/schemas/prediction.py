import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

PREDICTION_TYPE_PATTERN = "^(smoking_risk|habit_adherence)$"


class SmokingRiskRequest(BaseModel):
    """Mirrors the first few fields of SmokingEventCreate — this predicts
    the outcome of a craving the user hasn't logged yet, before it's
    decided."""

    trigger: str = Field(min_length=1, max_length=200)
    craving_intensity: int = Field(ge=1, le=10)
    stress_level: int | None = Field(default=None, ge=1, le=5)


class PredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    prediction_type: str
    predicted_probability: float | None
    confidence: str
    explanation: str
    created_at: datetime


class PredictionFeedbackCreate(BaseModel):
    actual_outcome: bool


class PredictionFeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    prediction_id: uuid.UUID
    actual_outcome: bool
    recorded_at: datetime


class ModelVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    prediction_type: str
    version: int
    algorithm: str
    training_sample_count: int
    training_accuracy: float | None
    trained_at: datetime
