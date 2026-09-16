import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Design decision (documented, not hidden): the master doc lists
# smoking_events, cravings, and triggers as separate tables/entities. They're
# modeled here as one SmokingEvent row per craving-to-outcome episode, with
# `trigger` as a free-text field rather than a separate lookup table — a
# trigger is whatever the user says caused the urge ("after lunch", "an
# argument", "boredom"), not a fixed taxonomy that benefits from being
# normalized into its own table. This is the same reasoning as the
# Memory/category merge in Phase 3 and the FinancialGoal/goal_type merge in
# Phase 6: one table, distinguished by columns, until a column genuinely
# needs a shape the others don't.
#
# This table never diagnoses nicotine dependence or any condition — it only
# ever stores what the user explicitly logged about a craving and what they
# did about it (see app/services/smoking_service.py and the safety
# boundaries in app/ai/personality.py). A "smoked" outcome is recorded
# exactly like every other outcome: no different code path, no shaming logic
# anywhere in this table or the service built on it.


class SmokingEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "smoking_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Free text — whatever the user says caused the craving. Not an enum:
    # section 10 asks the system to *detect* recurring triggers from what
    # users actually say, not to force them into a preset list.
    trigger: Mapped[str] = mapped_column(String(200), nullable=False)

    # 1-10, user-rated. Optional stress/mood context, same self-report
    # pattern as MoodLog — never inferred, only what the user entered.
    craving_intensity: Mapped[int] = mapped_column(Integer, nullable=False)
    stress_level: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5

    # Free-text situational context (location, who they were with, etc.),
    # entered only if the user chooses to share it.
    context: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # resisted | alternative_used | smoked — recorded neutrally. See
    # smoking_service for the no-shame handling of a "smoked" outcome.
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    alternative_action: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Optional structured reflection, filled in (by the user, in their own
    # words) using the failure-protocol sequence from section 5: what
    # happened, what was controllable, what caused it, what was learned.
    # Never auto-generated or put in the user's mouth by the AI.
    reflection_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SmokingEvent id={self.id} outcome={self.outcome}>"
