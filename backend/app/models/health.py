import uuid
from datetime import date, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Design decision (documented, not hidden): the master doc lists diet_logs,
# water_logs, sleep_logs, workout_logs, and mood_logs as five separate
# tables — unlike memories/lessons/behavior_patterns (Phase 3), these five
# genuinely have different shapes (a water log is just an amount + a
# timestamp; a sleep log is bedtime/wake_time/duration/quality; a mood log
# carries a journal entry). Grouping them in one file (like task.py holds
# Task+TaskLog) is purely a file-organization choice, not a schema merge.
#
# None of these tables diagnose anything. They only ever store what the user
# explicitly logged — see app/services/health_service.py and the safety
# boundaries in app/ai/personality.py.


class DietLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "diet_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # breakfast | lunch | dinner | snack
    meal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)

    # Both optional and user-entered — calorie/protein tracking is
    # configurable, never assumed or estimated by the system (section 11).
    calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protein_grams: Mapped[float | None] = mapped_column(Float, nullable=True)

    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DietLog id={self.id} meal_type={self.meal_type}>"


class WaterLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "water_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    amount_ml: Mapped[int] = mapped_column(Integer, nullable=False)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<WaterLog id={self.id} amount_ml={self.amount_ml}>"


class SleepLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One row per (user, sleep_date) — sleep_date is the morning a sleep
    session is attributed to (you log 'last night's sleep' on the date you
    woke up). Logging the same night twice updates in place rather than
    creating a duplicate, same idempotency pattern as HabitLog."""

    __tablename__ = "sleep_logs"
    __table_args__ = (
        # DB-level backstop for the same one-row-per-night rule
        # health_service.log_sleep enforces in application code — keeps a
        # race between two concurrent requests for the same night from ever
        # producing two rows.
        UniqueConstraint("user_id", "sleep_date", name="uq_sleep_logs_user_id_sleep_date"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    sleep_date: Mapped[date] = mapped_column(nullable=False, index=True)
    bedtime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    wake_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Derived from bedtime/wake_time when both are given, or entered
    # directly by the user when they only know the total — see
    # health_service.log_sleep.
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5, user-rated
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SleepLog id={self.id} sleep_date={self.sleep_date}>"


class WorkoutLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "workout_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    activity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    # low | medium | high
    intensity: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<WorkoutLog id={self.id} activity_type={self.activity_type}>"


class MoodLog(Base, UUIDPrimaryKeyMixin):
    """Mental-wellness check-in: mood + optional stress rating + optional
    free-text journal entry. Never used to diagnose anything — this is a
    self-report log, not a clinical instrument (see safety boundaries)."""

    __tablename__ = "mood_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # very_low | low | neutral | good | great
    mood: Mapped[str] = mapped_column(String(20), nullable=False)
    stress_level: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5, user-rated
    journal_entry: Mapped[str | None] = mapped_column(Text, nullable=True)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MoodLog id={self.id} mood={self.mood}>"
