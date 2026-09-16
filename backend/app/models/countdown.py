import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Section 17: countdowns are completely user-created and database-driven.
# No competition/hackathon/exam/deadline is ever hardcoded anywhere in this
# model or the service built on it — every row starts from a user's own
# POST /api/v1/countdowns call.

REPEAT_RULES = ("none", "daily", "weekly", "monthly", "yearly")
PRIORITIES = ("low", "medium", "high")

# Default reminder offsets (minutes before target_datetime) for a countdown
# that doesn't specify its own — one day before and one hour before. Still
# fully overridable per-countdown via notification_offsets_minutes; this is
# a sane default, not a hardcoded schedule.
DEFAULT_NOTIFICATION_OFFSETS_MINUTES = [1440, 60]


class Countdown(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "countdowns"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    target_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)

    # "none" means one-off. Anything else and the service rolls
    # target_datetime forward once it passes, rather than the countdown
    # silently going stale — see countdown_service.roll_forward_if_due.
    repeat_rule: Mapped[str] = mapped_column(String(10), default="none", nullable=False)

    # Minutes-before-target at which a deadline notification should be
    # generated (e.g. [1440, 60] = one day before and one hour before).
    # Stored as JSON so the same model works against both Aiven Postgres in
    # production and SQLite in tests, same reasoning as Habit.repeat_days.
    notification_offsets_minutes: Mapped[list[int]] = mapped_column(JSON, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Countdown id={self.id} title={self.title!r} target={self.target_datetime}>"
