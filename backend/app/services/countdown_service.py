"""
Countdown domain service (section 17).

Countdowns are plain, user-created CRUD — no countdown is ever seeded or
hardcoded (see app/models/countdown.py). The one piece of real behavior
beyond CRUD is repeat-rule rollover: a "daily"/"weekly"/"monthly"/"yearly"
countdown that has passed its target_datetime is advanced forward to its
next occurrence rather than just sitting there stale, so a recurring
countdown (e.g. "weekly review") keeps being a useful "time until" instead
of turning into a permanent negative number. This is deliberately plain
date arithmetic, not a full RFC 5545 recurrence engine — good enough for
the four rules the master doc actually asks for.
"""
import calendar
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.countdown import Countdown
from app.schemas.countdown import CountdownCreate, CountdownUpdate


class NotFoundError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware_utc(moment: datetime) -> datetime:
    """Same defensive normalization as smoking_service._as_aware_utc: SQLite
    (tests) doesn't round-trip tzinfo on a DateTime(timezone=True) column the
    way Postgres (production) does."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def _add_interval(moment: datetime, rule: str) -> datetime:
    if rule == "daily":
        return moment + timedelta(days=1)
    if rule == "weekly":
        return moment + timedelta(weeks=1)
    if rule == "monthly":
        month = moment.month + 1
        year = moment.year + (1 if month > 12 else 0)
        month = 1 if month > 12 else month
        day = min(moment.day, calendar.monthrange(year, month)[1])
        return moment.replace(year=year, month=month, day=day)
    if rule == "yearly":
        year = moment.year + 1
        day = moment.day
        if moment.month == 2 and moment.day == 29 and not calendar.isleap(year):
            day = 28
        return moment.replace(year=year, day=day)
    return moment  # "none" — unreachable in practice, callers check first


def roll_forward_if_due(countdown: Countdown, as_of: datetime | None = None) -> bool:
    """Advances target_datetime past `as_of` when the countdown repeats and
    has already passed. Returns True if it changed anything (caller is
    responsible for committing). A capped loop, not unbounded, in case a
    long-dormant countdown needs to jump forward many cycles at once."""
    as_of = as_of or _now()
    if countdown.repeat_rule == "none":
        return False

    changed = False
    target = _as_aware_utc(countdown.target_datetime)
    for _ in range(1000):
        if target > as_of:
            break
        target = _add_interval(target, countdown.repeat_rule)
        changed = True

    if changed:
        countdown.target_datetime = target
    return changed


def _get_owned_countdown(db: Session, user_id: uuid.UUID, countdown_id: uuid.UUID) -> Countdown:
    countdown = db.execute(
        select(Countdown).where(Countdown.id == countdown_id, Countdown.user_id == user_id)
    ).scalar_one_or_none()
    if countdown is None:
        raise NotFoundError("Countdown not found")
    return countdown


def create_countdown(db: Session, user_id: uuid.UUID, payload: CountdownCreate) -> Countdown:
    countdown = Countdown(user_id=user_id, **payload.model_dump())
    db.add(countdown)
    db.commit()
    db.refresh(countdown)
    return countdown


def list_countdowns(db: Session, user_id: uuid.UUID, active_only: bool = False) -> list[Countdown]:
    stmt = select(Countdown).where(Countdown.user_id == user_id)
    if active_only:
        stmt = stmt.where(Countdown.is_active.is_(True))
    countdowns = list(db.execute(stmt.order_by(Countdown.target_datetime.asc())).scalars())

    changed_any = False
    for countdown in countdowns:
        if roll_forward_if_due(countdown):
            db.add(countdown)
            changed_any = True
    if changed_any:
        db.commit()
        countdowns.sort(key=lambda c: c.target_datetime)

    return countdowns


def get_next_active_countdown(db: Session, user_id: uuid.UUID) -> Countdown | None:
    """The single soonest upcoming active countdown, for the home screen's
    "active countdown" element (section 16)."""
    now = _now()
    active = [c for c in list_countdowns(db, user_id, active_only=True) if _as_aware_utc(c.target_datetime) >= now]
    return active[0] if active else None


def get_countdown(db: Session, user_id: uuid.UUID, countdown_id: uuid.UUID) -> Countdown:
    countdown = _get_owned_countdown(db, user_id, countdown_id)
    if roll_forward_if_due(countdown):
        db.add(countdown)
        db.commit()
        db.refresh(countdown)
    return countdown


def update_countdown(
    db: Session, user_id: uuid.UUID, countdown_id: uuid.UUID, payload: CountdownUpdate
) -> Countdown:
    countdown = _get_owned_countdown(db, user_id, countdown_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(countdown, field, value)
    db.add(countdown)
    db.commit()
    db.refresh(countdown)
    return countdown


def delete_countdown(db: Session, user_id: uuid.UUID, countdown_id: uuid.UUID) -> None:
    countdown = _get_owned_countdown(db, user_id, countdown_id)
    db.delete(countdown)
    db.commit()
