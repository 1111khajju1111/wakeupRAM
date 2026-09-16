import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Section 18: scheduled, contextual, deadline, and habit-intervention
# notifications, generated deterministically (see
# app/services/notification_service.py) and never spammy — enforced here by
# per-user preferences (quiet hours, a daily cap, per-type opt-out) rather
# than every domain deciding its own notification policy independently.

NOTIFICATION_TYPES = ("scheduled", "contextual", "behavioral", "deadline", "habit_intervention")
NOTIFICATION_STATUSES = ("pending", "delivered", "dismissed", "actioned")

DEFAULT_ENABLED_TYPES = {t: True for t in NOTIFICATION_TYPES}
DEFAULT_MAX_PER_DAY = 6


class NotificationPreference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", name="uq_notification_preferences_user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Hour-of-day (0-23), server/local time as configured by the user. Both
    # null means no quiet hours are configured. Wraps past midnight when
    # start > end (e.g. 22 -> 7), handled in notification_service.
    quiet_hours_start_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quiet_hours_end_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)

    max_per_day: Mapped[int] = mapped_column(Integer, default=DEFAULT_MAX_PER_DAY, nullable=False)

    # {"scheduled": true, "contextual": true, "behavioral": true,
    #  "deadline": true, "habit_intervention": true} — per-type opt-out.
    enabled_types: Mapped[dict[str, bool]] = mapped_column(JSON, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<NotificationPreference user_id={self.user_id}>"


class Notification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe_key"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(String(1000), nullable=False)

    # What generated this notification, if anything (countdown | habit |
    # smoking_pattern | manual) plus the source row's id — lets the frontend
    # deep-link, and lets the engine dedupe against re-generating the same
    # underlying event.
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Idempotency key the generator sets (e.g. "countdown:<id>:60:2026-09-20")
    # so re-running the engine never creates a duplicate for the same
    # underlying trigger.
    dedupe_key: Mapped[str | None] = mapped_column(String(300), nullable=True)

    trigger_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Notification id={self.id} type={self.type} status={self.status}>"
