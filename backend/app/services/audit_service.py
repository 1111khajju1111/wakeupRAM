"""
Records sensitive-action audit events (master doc section 21).

`record_event` commits on its own, independent of the caller's transaction:
an audit entry for a failed login must survive even when the rest of that
request's DB work is about to be rolled back, and a bug in audit writing
must never be able to block or corrupt the primary operation it's
describing. Failures here are logged and swallowed for the same reason —
audit logging is a safety net, not a feature that should be able to break
login.
"""
import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.audit_log import AuditLog

logger = get_logger(__name__)


def record_event(
    db: Session,
    action: str,
    *,
    user_id: Optional[uuid.UUID] = None,
    status: str = "success",
    ip_address: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            status=status,
            ip_address=ip_address,
            event_metadata=metadata or {},
        )
        db.add(entry)
        db.commit()
    except Exception:  # noqa: BLE001 - audit logging must never break the caller
        db.rollback()
        logger.exception("audit_log_write_failed", extra={"action": action})
