"""
Declarative base plus shared mixins.

Every user-owned table gets:
- id (UUID primary key)
- created_at / updated_at (timestamps)
- owner enforcement happens at the query layer (see app/services), not just the schema —
  the mixin only guarantees the column exists.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    # Python-side default (microsecond precision) alongside server_default:
    # SQLite's CURRENT_TIMESTAMP (what func.now() compiles to there) only has
    # whole-second resolution, so rows created in the same request burst can
    # get identical timestamps and sort unpredictably. server_default remains
    # as a safety net for rows inserted outside the ORM.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )
