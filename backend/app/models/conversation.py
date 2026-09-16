import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Conversation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Which AI mode this conversation is currently using: friend | teacher |
    # commander | coach | financial_guide | health_coach | adaptive.
    mode: Mapped[str] = mapped_column(String(30), default="adaptive", nullable=False)

    # None for ordinary text chat (which always follows the user's standing
    # Profile.preferred_language). Set to "en" | "te" | "mixed" for a
    # conversation created by voice_call_service.start_call, so a call can
    # use a language different from the user's saved default for that one
    # call without changing their global preference. See
    # ai/ram_core.py::handle_user_message for where this is resolved —
    # NOT resolving it there was a real bug: a call explicitly started with
    # language="en" while the profile default was "te" still generated
    # Telugu-instructed replies, because the language argument was being
    # taken purely from the profile with no per-conversation override.
    language_override: Mapped[str | None] = mapped_column(String(10), nullable=True)

    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Conversation id={self.id} user_id={self.user_id} mode={self.mode}>"


class Message(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # "user" | "assistant" — kept as a plain string rather than an enum table
    # since it will never need arbitrary new values.
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Set only on assistant messages where generation failed and a fallback
    # string was returned instead of a real model response (see ram_core.py).
    is_fallback: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Python-side default (microsecond precision) rather than relying solely
    # on server_default=func.now(): SQLite's CURRENT_TIMESTAMP only has
    # whole-second resolution, so two messages saved in the same request
    # burst can otherwise get identical created_at and sort unpredictably.
    # server_default stays as a safety net for any row inserted outside the ORM.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Message id={self.id} role={self.role} conversation_id={self.conversation_id}>"
