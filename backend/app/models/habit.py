import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Habit(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "habits"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # daily | weekly — weekly habits use repeat_days for which weekdays count (0=Sun..6=Sat).
    # Stored as JSON (rather than a Postgres ARRAY) so the same model works against
    # both Aiven Postgres in production and SQLite in tests.
    frequency: Mapped[str] = mapped_column(String(10), default="daily", nullable=False)
    repeat_days: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)

    target_count_per_period: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    logs: Mapped[list["HabitLog"]] = relationship(
        "HabitLog", back_populates="habit", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Habit id={self.id} title={self.title!r} frequency={self.frequency}>"


class HabitLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "habit_logs"

    habit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("habits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    completed_on: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    habit: Mapped["Habit"] = relationship("Habit", back_populates="logs")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<HabitLog habit_id={self.habit_id} completed_on={self.completed_on}>"
