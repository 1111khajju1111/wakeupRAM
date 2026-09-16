import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

LANGUAGE_PATTERN = "^(en|te|mixed)$"


class VoiceCallCreate(BaseModel):
    # Defaults to the user's profile preferred_language in the service layer
    # when omitted — see voice_call_service.start_call.
    language: str | None = Field(default=None, pattern=LANGUAGE_PATTERN)
    recording_enabled: bool = False
    title: str | None = Field(default=None, max_length=200)


class VoiceCallRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    language: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None
    recording_enabled: bool
    recording_local_reference: str | None
    recording_duration_seconds: int | None


class VoiceCallEnd(BaseModel):
    # Both optional: a call ended without ever actually recording (or where
    # recording was enabled but produced nothing, e.g. permission denied
    # mid-call) reports neither field, which is the honest outcome — never
    # defaulted to a fabricated reference or duration.
    recording_local_reference: str | None = Field(default=None, max_length=500)
    recording_duration_seconds: int | None = Field(default=None, ge=0, le=24 * 60 * 60)
