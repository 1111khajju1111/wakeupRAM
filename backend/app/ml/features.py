"""
Feature engineering (section 9's "structured extraction... feature
engineering" step), one function pair per prediction_type:

- build_<type>_training_set: walks a user's own historical data into
  (feature_dict, label, occurred_at) rows for training.
- build_<type>_query_features: builds the same-shaped feature dict for a
  live "what's my risk right now" request, where the label doesn't exist
  yet.

Both use FEATURE_ORDER_<TYPE> to convert a named feature dict into the
plain float list app/ml/model.py operates on, so training and prediction
can never silently drift out of alignment (a dict key rename would break
loudly via KeyError rather than quietly shifting which weight applies to
which feature).

Time-of-day bucketing and trigger normalization are intentionally imported
from smoking_service rather than redefined here — one vocabulary for what
"evening" or "the same trigger" means, shared with detect_patterns.
"""
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.habit import Habit, HabitLog
from app.models.smoking import SmokingEvent
from app.services.habit_service import is_due_today
from app.services.smoking_service import _as_aware_utc, _normalized_trigger, _time_of_day_bucket

Features = dict[str, float]

# ---- Smoking risk ----

FEATURE_ORDER_SMOKING_RISK = [
    "craving_intensity",
    "stress_level",
    "stress_level_missing",
    "is_morning",
    "is_afternoon",
    "is_evening",
    "is_night",
    "trigger_repeat_count",
]

_DEFAULT_STRESS_LEVEL = 3.0  # midpoint of the 1-5 scale — a neutral guess, flagged via stress_level_missing


def _time_of_day_one_hot(bucket: str) -> dict[str, float]:
    return {
        "is_morning": 1.0 if bucket == "morning" else 0.0,
        "is_afternoon": 1.0 if bucket == "afternoon" else 0.0,
        "is_evening": 1.0 if bucket == "evening" else 0.0,
        "is_night": 1.0 if bucket == "night" else 0.0,
    }


def _smoking_features(
    craving_intensity: int, stress_level: int | None, occurred_at: datetime, trigger_repeat_count: int
) -> Features:
    return {
        "craving_intensity": float(craving_intensity),
        "stress_level": float(stress_level) if stress_level is not None else _DEFAULT_STRESS_LEVEL,
        "stress_level_missing": 0.0 if stress_level is not None else 1.0,
        **_time_of_day_one_hot(_time_of_day_bucket(_as_aware_utc(occurred_at))),
        "trigger_repeat_count": float(trigger_repeat_count),
    }


def build_smoking_risk_training_set(
    db: Session, user_id: uuid.UUID
) -> tuple[list[Features], list[bool], list[datetime]]:
    """Every logged craving is a labeled example (label = outcome == "smoked"),
    ordered chronologically so trigger_repeat_count only ever counts
    *earlier* occurrences of the same trigger — a training example must not
    see its own future."""
    events = list(
        db.execute(
            select(SmokingEvent).where(SmokingEvent.user_id == user_id).order_by(SmokingEvent.occurred_at.asc())
        ).scalars()
    )

    feature_rows: list[Features] = []
    labels: list[bool] = []
    occurred_ats: list[datetime] = []
    trigger_counts: Counter[str] = Counter()

    for event in events:
        normalized = _normalized_trigger(event.trigger)
        feature_rows.append(
            _smoking_features(
                event.craving_intensity, event.stress_level, event.occurred_at, trigger_counts[normalized]
            )
        )
        labels.append(event.outcome == "smoked")
        occurred_ats.append(event.occurred_at)
        trigger_counts[normalized] += 1

    return feature_rows, labels, occurred_ats


def build_smoking_risk_query_features(
    db: Session, user_id: uuid.UUID, trigger: str, craving_intensity: int, stress_level: int | None
) -> Features:
    """Live feature vector for "how likely am I to smoke if I don't
    intervene right now" — built from the same trigger a user is about to
    log, before the outcome exists."""
    normalized = _normalized_trigger(trigger)
    prior_events = db.execute(select(SmokingEvent).where(SmokingEvent.user_id == user_id)).scalars()
    trigger_repeat_count = sum(1 for e in prior_events if _normalized_trigger(e.trigger) == normalized)
    return _smoking_features(craving_intensity, stress_level, datetime.now(timezone.utc), trigger_repeat_count)


# ---- Habit adherence ----

FEATURE_ORDER_HABIT_ADHERENCE = [
    "is_sun",
    "is_mon",
    "is_tue",
    "is_wed",
    "is_thu",
    "is_fri",
    "is_sat",
    "rolling_completion_rate_14d",
    "current_streak_days",
]

_ROLLING_WINDOW_DAYS = 14
_MAX_TRAINING_DAYS_BACK = 90  # enough history for a personal model without an unbounded per-request walk


def _day_of_week_one_hot(day: date) -> dict[str, float]:
    # Sun=0..Sat=6, matching Habit.repeat_days' convention (see habit_service.is_due_today).
    sunday_indexed = (day.weekday() + 1) % 7
    labels = ["is_sun", "is_mon", "is_tue", "is_wed", "is_thu", "is_fri", "is_sat"]
    return {label: (1.0 if i == sunday_indexed else 0.0) for i, label in enumerate(labels)}


def _rolling_completion_rate(due_days_before: list[date], completed: set[date], as_of: date) -> float:
    window_start = as_of - timedelta(days=_ROLLING_WINDOW_DAYS)
    relevant = [d for d in due_days_before if window_start <= d < as_of]
    if not relevant:
        return 0.5  # no prior due-days yet to judge by — a neutral, honestly-uninformed midpoint
    return sum(1 for d in relevant if d in completed) / len(relevant)


def _streak_as_of(due_days_before: list[date], completed: set[date], as_of: date) -> float:
    """Consecutive due-days immediately before `as_of` (exclusive) that were
    completed — same walk-back logic as habit_service.calculate_current_streak,
    parameterized to an arbitrary historical point instead of always "today"
    so training examples reflect the streak as it actually stood on that day."""
    streak = 0
    for d in reversed(due_days_before):
        if d >= as_of:
            continue
        if d in completed:
            streak += 1
        else:
            break
    return float(streak)


def _due_days_between(habit: Habit, start: date, end_exclusive: date) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor < end_exclusive:
        if is_due_today(habit, cursor):
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def build_habit_adherence_training_set(
    db: Session, user_id: uuid.UUID, habit: Habit, today: date
) -> tuple[list[Features], list[bool], list[date]]:
    """One training example per due-day in the habit's own history (capped
    at _MAX_TRAINING_DAYS_BACK), labeled by whether it has a completion log.
    A day the habit wasn't due on is never a training example — "missed" is
    only meaningful relative to a day the habit actually asked something of
    the user."""
    created_date = habit.created_at.date()  # date portion is identical whether or not tzinfo is attached
    earliest = max(created_date, today - timedelta(days=_MAX_TRAINING_DAYS_BACK))

    completed: set[date] = set(
        db.execute(select(HabitLog.completed_on).where(HabitLog.habit_id == habit.id)).scalars()
    )

    all_due_days = _due_days_between(habit, earliest, today)

    feature_rows: list[Features] = []
    labels: list[bool] = []
    for i, day in enumerate(all_due_days):
        prior_due_days = all_due_days[:i]
        feature_rows.append(
            {
                **_day_of_week_one_hot(day),
                "rolling_completion_rate_14d": _rolling_completion_rate(prior_due_days, completed, day),
                "current_streak_days": _streak_as_of(prior_due_days, completed, day),
            }
        )
        labels.append(day in completed)

    return feature_rows, labels, all_due_days


def build_habit_adherence_query_features(db: Session, user_id: uuid.UUID, habit: Habit, as_of: date) -> Features:
    created_date = habit.created_at.date()  # date portion is identical whether or not tzinfo is attached
    earliest = max(created_date, as_of - timedelta(days=_MAX_TRAINING_DAYS_BACK))
    completed: set[date] = set(
        db.execute(select(HabitLog.completed_on).where(HabitLog.habit_id == habit.id)).scalars()
    )
    prior_due_days = _due_days_between(habit, earliest, as_of)
    return {
        **_day_of_week_one_hot(as_of),
        "rolling_completion_rate_14d": _rolling_completion_rate(prior_due_days, completed, as_of),
        "current_streak_days": _streak_as_of(prior_due_days, completed, as_of),
    }


# ---- Shared ----


def features_to_row(features: Features, feature_order: list[str]) -> list[float]:
    return [features[name] for name in feature_order]
