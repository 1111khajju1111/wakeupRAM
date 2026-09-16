"""
Smoking intervention domain service.

Section 10 asks for an intervention *system*, not a reminder: capture
trigger/stress/intensity/context/action for every craving, never shame a
"smoked" outcome, and over time detect recurring sequences so the system can
eventually intervene before a predictable craving window rather than only
after.

This is the first domain past plain CRUD logging (Phases 5/6): on top of the
same ownership-scoped create/list/update/delete pattern, `detect_patterns`
looks at a user's own recent events for recurring trigger / time-of-day
combinations tied to a "smoked" outcome, and — when a pattern clears a
frequency threshold — writes it into the existing Memory architecture via
memory_service.store_inferred_pattern (category=behavior_pattern,
source=ai_inferred). Because RAM Core already retrieves active memories into
every conversation's system prompt (see app/ai/ram_core.py), a detected
pattern surfaces to Ram naturally in the next conversation — labeled
INFERRED, never a settled fact — without conversation.py or ram_core.py
needing any smoking-specific code. That's the "hook into RAM Core" the
README flags as the one genuinely new piece here; everything else follows
the Phase 5/6 template.

Deliberately NOT machine learning — that's Phase 10. This is a transparent,
inspectable frequency count over the user's own logged events, and it always
exposes its evidence (occurrences, window) rather than a bare confidence
score. If there isn't enough data, detect_patterns returns an empty list —
the honest answer — never a fabricated insight.
"""
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.smoking import SmokingEvent
from app.schemas.smoking import SmokingEventCreate, SmokingEventUpdate
from app.services import memory_service

# A pattern needs at least this many matching "smoked" occurrences within the
# window before it's surfaced. Below this, noting it would be reading a
# trend into normal day-to-day variation.
PATTERN_MIN_OCCURRENCES = 3
PATTERN_WINDOW_DAYS = 30
SUMMARY_WINDOW_DAYS = 30

TIME_OF_DAY_BUCKETS = (
    ("early morning", 0, 6),
    ("morning", 6, 12),
    ("afternoon", 12, 17),
    ("evening", 17, 21),
    ("night", 21, 24),
)


class NotFoundError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware_utc(moment: datetime) -> datetime:
    """SQLite (used in tests, see tests/conftest.py) doesn't actually persist
    tzinfo on a DateTime(timezone=True) column — a round-tripped value comes
    back naive even though it was stored as UTC-aware. Postgres (production)
    preserves it. Normalize defensively here rather than let arithmetic
    against an aware "now" blow up depending on which database is behind
    it."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def _time_of_day_bucket(moment: datetime) -> str:
    hour = moment.hour
    for label, start, end in TIME_OF_DAY_BUCKETS:
        if start <= hour < end:
            return label
    return "night"  # pragma: no cover - unreachable, buckets cover 0-24


def _normalized_trigger(trigger: str) -> str:
    return trigger.strip().lower()


# ---- CRUD ----


def create_event(db: Session, user_id: uuid.UUID, payload: SmokingEventCreate) -> SmokingEvent:
    data = payload.model_dump()
    data["occurred_at"] = data.get("occurred_at") or _now()
    event = SmokingEvent(user_id=user_id, **data)
    db.add(event)
    db.commit()
    db.refresh(event)

    # Re-check for a recurring pattern every time a new event comes in,
    # rather than only on read — so a freshly-crossed threshold is available
    # to the very next conversation, not just the next time someone opens
    # the summary screen.
    detect_patterns(db, user_id)

    return event


def list_events(
    db: Session, user_id: uuid.UUID, start: datetime | None = None, end: datetime | None = None
) -> list[SmokingEvent]:
    stmt = select(SmokingEvent).where(SmokingEvent.user_id == user_id)
    if start is not None:
        stmt = stmt.where(SmokingEvent.occurred_at >= start)
    if end is not None:
        stmt = stmt.where(SmokingEvent.occurred_at < end)
    return list(db.execute(stmt.order_by(SmokingEvent.occurred_at.desc())).scalars())


def _get_owned_event(db: Session, user_id: uuid.UUID, event_id: uuid.UUID) -> SmokingEvent:
    event = db.execute(
        select(SmokingEvent).where(SmokingEvent.id == event_id, SmokingEvent.user_id == user_id)
    ).scalar_one_or_none()
    if event is None:
        raise NotFoundError("Smoking event not found")
    return event


def update_event(
    db: Session, user_id: uuid.UUID, event_id: uuid.UUID, payload: SmokingEventUpdate
) -> SmokingEvent:
    event = _get_owned_event(db, user_id, event_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def delete_event(db: Session, user_id: uuid.UUID, event_id: uuid.UUID) -> None:
    event = _get_owned_event(db, user_id, event_id)
    db.delete(event)
    db.commit()


# ---- Streak ----


def get_smoke_free_streak_days(db: Session, user_id: uuid.UUID, as_of: datetime | None = None) -> int | None:
    """Days since the most recent "smoked" outcome. None (not 0) when the
    user has never logged a "smoked" event at all — there's no honest streak
    number to report yet, so don't invent one. If they've never smoked-out
    but have logged resisted/alternative_used events, that's still a real
    streak measured from their first logged event, not an unbounded claim."""
    as_of = as_of or _now()

    last_smoked = db.execute(
        select(SmokingEvent)
        .where(SmokingEvent.user_id == user_id, SmokingEvent.outcome == "smoked")
        .order_by(SmokingEvent.occurred_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if last_smoked is not None:
        return max(0, (as_of - _as_aware_utc(last_smoked.occurred_at)).days)

    earliest_event = db.execute(
        select(SmokingEvent)
        .where(SmokingEvent.user_id == user_id)
        .order_by(SmokingEvent.occurred_at.asc())
        .limit(1)
    ).scalar_one_or_none()

    if earliest_event is None:
        return None  # nothing logged yet — unknown, not zero

    return max(0, (as_of - _as_aware_utc(earliest_event.occurred_at)).days)


# ---- Pattern detection ----


def detect_patterns(db: Session, user_id: uuid.UUID) -> list[dict]:
    """Deterministic frequency analysis over the user's own "smoked" events
    in the last PATTERN_WINDOW_DAYS. Any pattern clearing
    PATTERN_MIN_OCCURRENCES is written into Memory as an ai_inferred
    behavior_pattern (see module docstring) so it surfaces in the next
    conversation, and is also returned here for the summary endpoint to
    display directly. Returns [] — not a guess — when there isn't enough
    data yet."""
    window_start = _now() - timedelta(days=PATTERN_WINDOW_DAYS)
    smoked_events = list(
        db.execute(
            select(SmokingEvent).where(
                SmokingEvent.user_id == user_id,
                SmokingEvent.outcome == "smoked",
                SmokingEvent.occurred_at >= window_start,
            )
        ).scalars()
    )

    if len(smoked_events) < PATTERN_MIN_OCCURRENCES:
        return []

    trigger_counts: Counter[str] = Counter(_normalized_trigger(e.trigger) for e in smoked_events)
    time_bucket_counts: Counter[str] = Counter(_time_of_day_bucket(e.occurred_at) for e in smoked_events)
    combo_counts: Counter[tuple[str, str]] = Counter(
        (_normalized_trigger(e.trigger), _time_of_day_bucket(e.occurred_at)) for e in smoked_events
    )

    patterns: list[dict] = []

    for trigger, count in trigger_counts.most_common():
        if count < PATTERN_MIN_OCCURRENCES:
            continue
        identity_prefix = f'Smoking has followed the trigger "{trigger}"'
        description = f"{identity_prefix} {count} times in the last {PATTERN_WINDOW_DAYS} days."
        patterns.append(
            {
                "pattern_type": "trigger",
                "description": description,
                "occurrences": count,
                "window_days": PATTERN_WINDOW_DAYS,
                "identity_prefix": identity_prefix,
            }
        )

    for time_bucket, count in time_bucket_counts.most_common():
        if count < PATTERN_MIN_OCCURRENCES:
            continue
        identity_prefix = f"Smoking has happened during the {time_bucket}"
        description = f"{identity_prefix} {count} times in the last {PATTERN_WINDOW_DAYS} days."
        patterns.append(
            {
                "pattern_type": "time_of_day",
                "description": description,
                "occurrences": count,
                "window_days": PATTERN_WINDOW_DAYS,
                "identity_prefix": identity_prefix,
            }
        )

    for (trigger, time_bucket), count in combo_counts.most_common():
        if count < PATTERN_MIN_OCCURRENCES:
            continue
        identity_prefix = f'Smoking has followed "{trigger}" during the {time_bucket} specifically,'
        description = (
            f"{identity_prefix} {count} times in the last {PATTERN_WINDOW_DAYS} days — a more specific "
            "risk window than either factor alone."
        )
        patterns.append(
            {
                "pattern_type": "trigger_and_time_of_day",
                "description": description,
                "occurrences": count,
                "window_days": PATTERN_WINDOW_DAYS,
                "identity_prefix": identity_prefix,
            }
        )

    for pattern in patterns:
        # More occurrences -> higher confidence, capped well short of 1.0:
        # this is a frequency count over a limited window, never certainty.
        confidence = min(0.85, 0.35 + 0.1 * pattern["occurrences"])
        # The rendered description embeds a live count ("...3 times...")
        # that changes on every new event, which would defeat
        # store_inferred_pattern's exact-content dedup and pile up a fresh
        # near-duplicate memory each time the count ticks up. Supersede any
        # earlier variant of THIS SAME pattern (same type + trigger/time
        # identity, different count) first, using a prefix that stops right
        # before the part that varies.
        identity_prefix = pattern["identity_prefix"]
        memory_service.supersede_stale_variants(
            db, user_id, "behavior_pattern", identity_prefix, pattern["description"]
        )
        memory_service.store_inferred_pattern(db, user_id, pattern["description"], confidence)

    return patterns


# ---- Summary ----


def get_summary(db: Session, user_id: uuid.UUID) -> dict:
    window_start = _now() - timedelta(days=SUMMARY_WINDOW_DAYS)
    recent_events = list_events(db, user_id, start=window_start)

    # last_event is "most recent ever", independent of the summary window —
    # if the user's last log was 40 days ago, that's still the honest answer,
    # not None just because it falls outside the 30-day counters above.
    most_recent_ever = db.execute(
        select(SmokingEvent)
        .where(SmokingEvent.user_id == user_id)
        .order_by(SmokingEvent.occurred_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    outcome_counts = Counter(e.outcome for e in recent_events)
    patterns = detect_patterns(db, user_id)

    return {
        "window_days": SUMMARY_WINDOW_DAYS,
        "total_events": len(recent_events),
        "smoked_count": outcome_counts.get("smoked", 0),
        "resisted_count": outcome_counts.get("resisted", 0),
        "alternative_used_count": outcome_counts.get("alternative_used", 0),
        "smoke_free_streak_days": get_smoke_free_streak_days(db, user_id),
        "last_event": most_recent_ever,
        "detected_patterns": patterns,
    }
