import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, func
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Task(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tasks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goals.id", ondelete="SET NULL"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # low | medium | high — set by the user, never inferred silently
    priority: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)

    # pending | completed | skipped
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    # User-flagged as the single "today's mission" shown on the home screen.
    # Enforced as at most one true per (user_id, due_date) at the service layer.
    is_daily_mission: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    goal: Mapped["Goal | None"] = relationship("Goal", back_populates="tasks")
    logs: Mapped[list["TaskLog"]] = relationship(
        "TaskLog", back_populates="task", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Task id={self.id} title={self.title!r} status={self.status}>"


class TaskLog(Base, UUIDPrimaryKeyMixin):
    """Append-only history of what happened to a task — completions, skips,
    reschedules. Feeds the future behavioral-pattern/ML pipeline (Phase 10)."""

    __tablename__ = "task_logs"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # completed | skipped | rescheduled
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped["Task"] = relationship("Task", back_populates="logs")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TaskLog task_id={self.task_id} action={self.action}>"
