import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    display_name: str | None
    preferred_language: str
    theme_preference: str
    timezone: str
    onboarding_completed: bool


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    preferred_language: str | None = Field(default=None, pattern="^(en|te)$")
    theme_preference: str | None = Field(default=None, pattern="^(light|dark|system)$")
    timezone: str | None = Field(default=None, max_length=64)
    onboarding_completed: bool | None = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    is_active: bool
    is_verified: bool
    created_at: datetime
    profile: ProfileRead | None = None
