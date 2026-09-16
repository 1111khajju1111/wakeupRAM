"""
Structured logging (Phase 13).

Design notes:
- JSON lines to stdout, the format every managed platform (Render, Vercel,
  Docker, journald) captures and indexes without extra agents.
- A `RedactingFilter` strips known-sensitive field names before a record is
  emitted, so a future `logger.info("...", extra={...})` call can't
  accidentally leak a password/token/API key into logs even if a caller
  forgets to scrub it first — belt-and-suspenders on top of "don't log
  secrets" being a code-review rule.
- Request correlation: `main.py`'s middleware stamps a `request_id` into a
  contextvar; the formatter pulls it in automatically so every log line
  inside one request can be grepped together without passing the id through
  every function signature.
- This intentionally does NOT log full request/response bodies — personal
  health/finance/conversation content must never end up in log storage
  (section 21/27 of the master doc). Only route, status, duration, user id,
  and explicit event names are logged.
"""
import contextvars
import json
import logging
import sys
import time
from typing import Any

from app.core.config import get_settings

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

_REDACT_KEYS = {
    "password",
    "hashed_password",
    "plain_password",
    "access_token",
    "refresh_token",
    "authorization",
    "jwt_secret_key",
    "groq_api_key",
    "google_api_key",
}


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for key in list(vars(record).keys()):
            if key.lower() in _REDACT_KEYS:
                setattr(record, key, "[REDACTED]")
        return True


class JsonFormatter(logging.Formatter):
    # Standard LogRecord attributes we never want echoed back as "extra"
    # fields, since they're already represented explicitly below.
    _RESERVED = set(logging.LogRecord(None, None, "", 0, "", (), None).__dict__.keys()) | {"message"}

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        for key, value in vars(record).items():
            if key in self._RESERVED or key.startswith("_"):
                continue
            if key.lower() in _REDACT_KEYS:
                value = "[REDACTED]"
            payload[key] = value

        return json.dumps(payload, default=str)


def configure_logging() -> None:
    settings = get_settings()
    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter())
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Quiet noisy third-party loggers down to warnings only; app code and
    # uvicorn's own access/error logs still flow through at INFO.
    for noisy in ("sqlalchemy.engine", "passlib", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class Timer:
    """Small helper for logging an operation's duration in milliseconds."""

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.elapsed_ms = round((time.perf_counter() - self._start) * 1000, 2)
