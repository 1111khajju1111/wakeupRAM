import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Design decision (documented, not hidden): the master doc lists memories,
# lessons, and behavior_patterns as separate tables. For Phase 3 they are
# modeled as one Memory table distinguished by `category`, since all three
# share identical metadata (source, confidence, relevance, timestamps,
# status) and identical access patterns (retrieve-by-user, retrieve-by-
# category, decay/expire). Splitting them into physically separate tables
# with no behavioral difference would be duplication without benefit; if a
# category later needs fields the others don't, it should be split out then.


class Memory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "memories"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # fact | preference | goal_context | habit_context | lesson |
    # behavior_pattern | context
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # user_stated | ai_inferred | conversation_extracted
    source: Mapped[str] = mapped_column(String(30), nullable=False)

    # 0.0-1.0. user_stated facts should be created at 1.0; inferred/extracted
    # memories start lower and are never silently promoted to user_stated.
    confidence: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    # 0.0-1.0, a simple recency/frequency-of-use weight — real ranking-by-
    # embedding retrieval is future ML work (see Phase 10), this is the
    # honest placeholder until then.
    relevance: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)

    # active | archived | superseded — user-control state. A user can archive
    # or delete a memory; superseded is set when a newer memory replaces it.
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Memory id={self.id} category={self.category} status={self.status}>"
