"""
Central application configuration.

Everything here is sourced from environment variables (via .env in dev).
No secrets, URLs, or environment-specific values are ever hardcoded in code —
per the Wake Up Ram zero-hardcoding requirement.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    DATABASE_URL: str
    DATABASE_SSL_MODE: str = "prefer"

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    CORS_ALLOWED_ORIGINS: str = ""

    RATE_LIMIT_DEFAULT: str = "100/minute"

    AI_PROVIDER: str = "groq"
    GROQ_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    AI_MODEL_NAME: str = "openai/gpt-oss-120b"
    AI_MAX_TOKENS: int = 1024
    AI_DEFAULT_MODE: str = "adaptive"
    AI_MEMORY_RETRIEVAL_LIMIT: int = 20

    STT_PROVIDER: str = "google"
    STT_MODEL_NAME: str = "gemini-3.5-transcribe-live"
    TTS_PROVIDER: str = "google"
    TTS_MODEL_NAME: str = "gemini-3.1-flash-tts-preview"
    GOOGLE_API_KEY: str = ""

    BACKEND_BASE_URL: str = "https://wakeupram.onrender.com"
    FRONTEND_BASE_URL: str = "https://wakeup-ram.vercel.app"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


@lru_cache
def get_settings() -> "Settings":
    # lru_cache means the .env / environment is read once per process,
    # which is fine because env vars don't change at runtime in a deployed container.
    return Settings()
