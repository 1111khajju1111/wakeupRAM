import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Profile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Everything the user configured about themselves and their experience.
    No field here is ever defaulted to a hardcoded real name, goal, or habit —
    all of it originates from user input during onboarding/settings.
    """

    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)  # "en" | "te"
    theme_preference: Mapped[str] = mapped_column(String(16), default="system", nullable=False)  # light|dark|system
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)

    onboarding_completed: Mapped[bool] = mapped_column(default=False, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="profile")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Profile user_id={self.user_id} display_name={self.display_name!r}>"
