import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Goal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A user-defined outcome, e.g. 'Quit smoking' or 'Finish BTech project'.
    Never seeded or hardcoded — always created via user input."""

    __tablename__ = "goals"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # active | completed | abandoned
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="goal")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Goal id={self.id} title={self.title!r} status={self.status}>"
