"""
Notification engine (section 18).

This is the piece section 18 asks be more than a reminder list: scheduled,
contextual, deadline, and habit-intervention notifications, generated
deterministically from a user's own data, gated by per-user preferences
(quiet hours, a daily cap, per-type opt-out) so the system stays
configurable and non-spammy rather than firing everything the moment it's
technically true.

Three sources are wired up here, each reusing an existing service rather
than duplicating its logic:
  - deadline: upcoming Countdown targets (section 17), at each countdown's
    own configured offsets.
  - habit_intervention: a habit that's due today, not yet logged, once the
    day has reached a risk hour — reusing habit_service.is_due_today /
    calculate streak data, not a second copy of habit due-logic.
  - behavioral: a detected smoking pattern (Phase 7's
    smoking_service.detect_patterns) that's cleared its threshold today —
    this is exactly the "Phase 7's detect_patterns output should start
    earning its keep" hook the Phase 7 README note asked for.

Generation is on-demand (POST /api/v1/notifications/refresh), not a
background cron — there's no task scheduler/worker in this codebase yet
(that's Phase 13 infra). In production this same generate_for_user function
is what a scheduled job would call per user; nothing about its logic
changes when that scheduler exists, only what calls it and how often.

Every candidate carries a dedupe_key so re-running generation (whether from
a user opening the app twice or a future scheduler running every few
minutes) never creates duplicate notifications for the same underlying
event.
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.notification import (
    DEFAULT_ENABLED_TYPES,
    DEFAULT_MAX_PER_DAY,
    Notification,
    NotificationPreference,
)
from app.schemas.notification import NotificationPreferenceUpdate, NotificationStatusUpdate
from app.services import countdown_service, habit_service, smoking_service

# Habit-intervention notifications only fire once the day has reached this
# local hour — nudging about an undone habit at 7am would be premature, not
# an intervention. A constant, not a magic number scattered inline; tune
# here if it needs to change.
HABIT_RISK_HOUR = 18


class NotFoundError(Exception):
    pass


class InvalidStatusTransitionError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware_utc(moment: datetime) -> datetime:
    """Same defensive normalization used in smoking_service/countdown_service:
    SQLite (tests) doesn't round-trip tzinfo the way Postgres (production)
    does."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def _format_offset(offset_minutes: int) -> str:
    if offset_minutes <= 0:
        return "now"
    if offset_minutes % 1440 == 0:
        days = offset_minutes // 1440
        return f"{days} day{'s' if days != 1 else ''}"
    if offset_minutes % 60 == 0:
        hours = offset_minutes // 60
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{offset_minutes} minute{'s' if offset_minutes != 1 else ''}"


# ---- Preferences ----


def get_preferences(db: Session, user_id: uuid.UUID) -> NotificationPreference:
    pref = db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    ).scalar_one_or_none()
    if pref is None:
        pref = NotificationPreference(
            user_id=user_id,
            max_per_day=DEFAULT_MAX_PER_DAY,
            enabled_types=dict(DEFAULT_ENABLED_TYPES),
        )
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref


def update_preferences(
    db: Session, user_id: uuid.UUID, payload: NotificationPreferenceUpdate
) -> NotificationPreference:
    pref = get_preferences(db, user_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(pref, field, value)
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref


def _is_quiet_hours(pref: NotificationPreference, moment: datetime) -> bool:
    start, end = pref.quiet_hours_start_hour, pref.quiet_hours_end_hour
    if start is None or end is None or start == end:
        return False
    hour = moment.hour
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end  # wraps past midnight, e.g. 22 -> 7


def _defer_past_quiet_hours(pref: NotificationPreference, moment: datetime) -> datetime:
    if not _is_quiet_hours(pref, moment):
        return moment
    candidate = moment.replace(hour=pref.quiet_hours_end_hour, minute=0, second=0, microsecond=0)
    if candidate <= moment:
        candidate += timedelta(days=1)
    return candidate


# ---- Candidate generation (each source is independently testable) ----


def _deadline_candidates(db: Session, user_id: uuid.UUID, now: datetime) -> list[dict]:
    candidates: list[dict] = []
    for countdown in countdown_service.list_countdowns(db, user_id, active_only=True):
        target = _as_aware_utc(countdown.target_datetime)
        for offset in countdown.notification_offsets_minutes:
            threshold = target - timedelta(minutes=offset)
            if now < threshold:
                continue
            candidates.append(
                {
                    "type": "deadline",
                    "title": countdown.title,
                    "body": f'"{countdown.title}" is {_format_offset(offset)} away.',
                    "source_type": "countdown",
                    "source_id": countdown.id,
                    "dedupe_key": f"countdown:{countdown.id}:{offset}:{target.date().isoformat()}",
                    "trigger_at": threshold,
                }
            )
    return candidates


def _habit_intervention_candidates(db: Session, user_id: uuid.UUID, now: datetime) -> list[dict]:
    if now.hour < HABIT_RISK_HOUR:
        return []

    today = now.date()
    candidates: list[dict] = []
    for habit in habit_service.list_habits(db, user_id, active_only=True):
        if not habit_service.is_due_today(habit, today):
            continue
        completed_today = any(log.completed_on == today for log in habit.logs)
        if completed_today:
            continue
        candidates.append(
            {
                "type": "habit_intervention",
                "title": habit.title,
                "body": f'"{habit.title}" hasn\'t been logged yet today.',
                "source_type": "habit",
                "source_id": habit.id,
                "dedupe_key": f"habit:{habit.id}:{today.isoformat()}",
                "trigger_at": now,
            }
        )
    return candidates


def _behavioral_candidates(db: Session, user_id: uuid.UUID, now: datetime) -> list[dict]:
    today = now.date()
    candidates: list[dict] = []
    for pattern in smoking_service.detect_patterns(db, user_id):
        candidates.append(
            {
                "type": "behavioral",
                "title": "Smoking pattern noticed",
                "body": pattern["description"],
                "source_type": "smoking_pattern",
                "source_id": None,
                "dedupe_key": f"smoking_pattern:{pattern['pattern_type']}:{today.isoformat()}",
                "trigger_at": now,
            }
        )
    return candidates


# ---- Engine ----


def generate_for_user(db: Session, user_id: uuid.UUID, now: datetime | None = None) -> list[Notification]:
    """`now` is injectable for tests that need deterministic hour-of-day
    behavior (habit-intervention risk hour, quiet hours); production call
    sites simply omit it and get the real current time."""
    now = now or _now()
    pref = get_preferences(db, user_id)

    # Priority order: an imminent deadline matters more than a same-day
    # habit nudge or a behavioral observation, so if the daily cap is close
    # to full, deadlines are the ones that still get through.
    candidates = (
        _deadline_candidates(db, user_id, now)
        + _habit_intervention_candidates(db, user_id, now)
        + _behavioral_candidates(db, user_id, now)
    )
    candidates = [c for c in candidates if pref.enabled_types.get(c["type"], True)]

    existing_keys = set(
        db.execute(
            select(Notification.dedupe_key).where(
                Notification.user_id == user_id, Notification.dedupe_key.isnot(None)
            )
        ).scalars()
    )
    candidates = [c for c in candidates if c["dedupe_key"] not in existing_keys]

    # Use now.date() (not date.today()) — everything else in this function
    # is computed relative to the injected `now`, and Notification.created_at
    # is stored in UTC. date.today() returns the server's local wall-clock
    # date, which can silently disagree with now.date() near a day boundary
    # or on a server not running in UTC, shifting which notifications count
    # toward "today's" quota.
    day_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
    today_count = db.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.created_at >= day_start)
    ).scalar_one()
    remaining_quota = max(0, pref.max_per_day - today_count)

    created: list[Notification] = []
    for candidate in candidates[:remaining_quota]:
        notification = Notification(
            user_id=user_id,
            type=candidate["type"],
            title=candidate["title"],
            body=candidate["body"],
            source_type=candidate["source_type"],
            source_id=candidate["source_id"],
            dedupe_key=candidate["dedupe_key"],
            trigger_at=_defer_past_quiet_hours(pref, candidate["trigger_at"]),
            status="pending",
        )
        db.add(notification)
        created.append(notification)

    if created:
        db.commit()
        for notification in created:
            db.refresh(notification)

    return created


# ---- CRUD / status ----


def list_notifications(db: Session, user_id: uuid.UUID, status: str | None = None) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if status is not None:
        stmt = stmt.where(Notification.status == status)
    return list(db.execute(stmt.order_by(Notification.trigger_at.desc())).scalars())


def _get_owned_notification(db: Session, user_id: uuid.UUID, notification_id: uuid.UUID) -> Notification:
    notification = db.execute(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
    ).scalar_one_or_none()
    if notification is None:
        raise NotFoundError("Notification not found")
    return notification


def update_status(
    db: Session, user_id: uuid.UUID, notification_id: uuid.UUID, payload: NotificationStatusUpdate
) -> Notification:
    notification = _get_owned_notification(db, user_id, notification_id)
    if notification.status == "dismissed":
        # A dismissed notification is final — nothing to transition to.
        raise InvalidStatusTransitionError("Notification already dismissed")

    notification.status = payload.status
    now = _now()
    if payload.status == "delivered" and notification.delivered_at is None:
        notification.delivered_at = now
    if payload.status == "actioned":
        notification.actioned_at = now
        if notification.delivered_at is None:
            notification.delivered_at = now

    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification
