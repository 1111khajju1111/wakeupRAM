"""
Audit log for sensitive account/security actions (master doc section 21:
"Maintain audit logs for sensitive actions").

Deliberately separate from the structured request logging in
app/core/logging.py: that's operational (routes, latency, errors) and
short-retention; this is a durable, queryable record scoped to actions with
real account/security/privacy weight — login, registration, password
change, token refresh failure, data export, account/data deletion.

What this table does NOT store: request/response bodies, health/finance/
conversation content, or anything from the fields in RedactingFilter. Only
the action name, who did it, when, and a small non-sensitive metadata blob
(e.g. {"reason": "invalid_password"} for a failed login).
"""
import uuid

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuditLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    # Nullable: some events (e.g. a login attempt against an email that
    # doesn't exist) have no known user to attach to yet.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog action={self.action} user_id={self.user_id} status={self.status}>"
