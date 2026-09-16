import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.notification import DEFAULT_ENABLED_TYPES, NOTIFICATION_TYPES

STATUS_UPDATE_PATTERN = "^(delivered|dismissed|actioned)$"


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    title: str
    body: str
    source_type: str | None
    source_id: uuid.UUID | None
    trigger_at: datetime
    status: str
    created_at: datetime
    delivered_at: datetime | None
    actioned_at: datetime | None


class NotificationStatusUpdate(BaseModel):
    status: str = Field(pattern=STATUS_UPDATE_PATTERN)


class NotificationPreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    quiet_hours_start_hour: int | None
    quiet_hours_end_hour: int | None
    max_per_day: int
    enabled_types: dict[str, bool]


class NotificationPreferenceUpdate(BaseModel):
    quiet_hours_start_hour: int | None = Field(default=None, ge=0, le=23)
    quiet_hours_end_hour: int | None = Field(default=None, ge=0, le=23)
    max_per_day: int | None = Field(default=None, ge=1, le=50)
    enabled_types: dict[str, bool] | None = None

    @field_validator("enabled_types")
    @classmethod
    def _known_types_only(cls, value: dict[str, bool] | None) -> dict[str, bool] | None:
        if value is None:
            return value
        unknown = set(value) - set(NOTIFICATION_TYPES)
        if unknown:
            raise ValueError(f"Unknown notification type(s): {sorted(unknown)}")
        # Merge onto the full default set rather than accepting a partial
        # dict, so an omitted type doesn't silently fall out of storage.
        merged = dict(DEFAULT_ENABLED_TYPES)
        merged.update(value)
        return merged
