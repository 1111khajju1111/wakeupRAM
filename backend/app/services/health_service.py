"""
Health domain service: diet, water, sleep, workout, and mood logging.

Consistent with the rest of the app: every read/write is scoped by user_id at
the query layer (see _get_owned_* helpers), nothing here diagnoses or
estimates on the user's behalf, and "today" is computed the same
server-local way app/api/v1/endpoints/today.py already does for tasks/habits
— true per-user-timezone "today" is deferred to when Profile.timezone is
actually wired through the request path, not introduced piecemeal here.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.health import DietLog, MoodLog, SleepLog, WaterLog, WorkoutLog
from app.schemas.health import (
    DietLogCreate,
    DietLogUpdate,
    MoodLogCreate,
    SleepLogCreate,
    SleepLogUpdate,
    WaterLogCreate,
    WorkoutLogCreate,
    WorkoutLogUpdate,
)


class NotFoundError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---- Diet ----


def create_diet_log(db: Session, user_id: uuid.UUID, payload: DietLogCreate) -> DietLog:
    data = payload.model_dump()
    data["logged_at"] = data.get("logged_at") or _now()
    log = DietLog(user_id=user_id, **data)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def list_diet_logs(
    db: Session, user_id: uuid.UUID, start: datetime | None = None, end: datetime | None = None
) -> list[DietLog]:
    stmt = select(DietLog).where(DietLog.user_id == user_id)
    if start is not None:
        stmt = stmt.where(DietLog.logged_at >= start)
    if end is not None:
        stmt = stmt.where(DietLog.logged_at < end)
    return list(db.execute(stmt.order_by(DietLog.logged_at.desc())).scalars())


def _get_owned_diet_log(db: Session, user_id: uuid.UUID, log_id: uuid.UUID) -> DietLog:
    log = db.execute(
        select(DietLog).where(DietLog.id == log_id, DietLog.user_id == user_id)
    ).scalar_one_or_none()
    if log is None:
        raise NotFoundError("Diet log not found")
    return log


def update_diet_log(db: Session, user_id: uuid.UUID, log_id: uuid.UUID, payload: DietLogUpdate) -> DietLog:
    log = _get_owned_diet_log(db, user_id, log_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(log, field, value)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def delete_diet_log(db: Session, user_id: uuid.UUID, log_id: uuid.UUID) -> None:
    log = _get_owned_diet_log(db, user_id, log_id)
    db.delete(log)
    db.commit()


# ---- Water ----


def create_water_log(db: Session, user_id: uuid.UUID, payload: WaterLogCreate) -> WaterLog:
    data = payload.model_dump()
    data["logged_at"] = data.get("logged_at") or _now()
    log = WaterLog(user_id=user_id, **data)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def list_water_logs(
    db: Session, user_id: uuid.UUID, start: datetime | None = None, end: datetime | None = None
) -> list[WaterLog]:
    stmt = select(WaterLog).where(WaterLog.user_id == user_id)
    if start is not None:
        stmt = stmt.where(WaterLog.logged_at >= start)
    if end is not None:
        stmt = stmt.where(WaterLog.logged_at < end)
    return list(db.execute(stmt.order_by(WaterLog.logged_at.desc())).scalars())


def _get_owned_water_log(db: Session, user_id: uuid.UUID, log_id: uuid.UUID) -> WaterLog:
    log = db.execute(
        select(WaterLog).where(WaterLog.id == log_id, WaterLog.user_id == user_id)
    ).scalar_one_or_none()
    if log is None:
        raise NotFoundError("Water log not found")
    return log


def delete_water_log(db: Session, user_id: uuid.UUID, log_id: uuid.UUID) -> None:
    log = _get_owned_water_log(db, user_id, log_id)
    db.delete(log)
    db.commit()


# ---- Sleep ----


def log_sleep(db: Session, user_id: uuid.UUID, payload: SleepLogCreate) -> SleepLog:
    """One log per (user, sleep_date). Logging the same night again updates
    the existing row rather than creating a duplicate — same idempotency
    pattern as habit_service.log_habit_completion, for the same reason: a
    double-submit or an edited re-log must never look like two nights."""
    existing = db.execute(
        select(SleepLog).where(SleepLog.user_id == user_id, SleepLog.sleep_date == payload.sleep_date)
    ).scalar_one_or_none()

    duration = _resolve_duration(payload.bedtime, payload.wake_time, payload.duration_minutes)

    if existing:
        existing.bedtime = payload.bedtime
        existing.wake_time = payload.wake_time
        existing.duration_minutes = duration
        existing.quality = payload.quality
        existing.notes = payload.notes
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    log = SleepLog(
        user_id=user_id,
        sleep_date=payload.sleep_date,
        bedtime=payload.bedtime,
        wake_time=payload.wake_time,
        duration_minutes=duration,
        quality=payload.quality,
        notes=payload.notes,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def _resolve_duration(
    bedtime: datetime | None, wake_time: datetime | None, explicit_duration: int | None
) -> int | None:
    """Explicit duration wins if given (the user may only know the total, not
    exact clock times). Otherwise derive it from bedtime/wake_time when both
    are present. A negative result (wake_time before bedtime, e.g. bad input)
    is clamped to 0 rather than stored as a nonsensical negative duration."""
    if explicit_duration is not None:
        return explicit_duration
    if bedtime and wake_time:
        delta_minutes = int((wake_time - bedtime).total_seconds() // 60)
        return max(0, delta_minutes)
    return None


def list_sleep_logs(
    db: Session, user_id: uuid.UUID, start: date | None = None, end: date | None = None
) -> list[SleepLog]:
    stmt = select(SleepLog).where(SleepLog.user_id == user_id)
    if start is not None:
        stmt = stmt.where(SleepLog.sleep_date >= start)
    if end is not None:
        stmt = stmt.where(SleepLog.sleep_date <= end)
    return list(db.execute(stmt.order_by(SleepLog.sleep_date.desc())).scalars())


def _get_owned_sleep_log(db: Session, user_id: uuid.UUID, log_id: uuid.UUID) -> SleepLog:
    log = db.execute(
        select(SleepLog).where(SleepLog.id == log_id, SleepLog.user_id == user_id)
    ).scalar_one_or_none()
    if log is None:
        raise NotFoundError("Sleep log not found")
    return log


def update_sleep_log(db: Session, user_id: uuid.UUID, log_id: uuid.UUID, payload: SleepLogUpdate) -> SleepLog:
    log = _get_owned_sleep_log(db, user_id, log_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(log, field, value)
    if "duration_minutes" not in update_data:
        log.duration_minutes = _resolve_duration(log.bedtime, log.wake_time, None)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def delete_sleep_log(db: Session, user_id: uuid.UUID, log_id: uuid.UUID) -> None:
    log = _get_owned_sleep_log(db, user_id, log_id)
    db.delete(log)
    db.commit()


def get_latest_sleep_log(db: Session, user_id: uuid.UUID) -> SleepLog | None:
    stmt = select(SleepLog).where(SleepLog.user_id == user_id).order_by(SleepLog.sleep_date.desc()).limit(1)
    return db.execute(stmt).scalar_one_or_none()


# ---- Workout ----


def create_workout_log(db: Session, user_id: uuid.UUID, payload: WorkoutLogCreate) -> WorkoutLog:
    data = payload.model_dump()
    data["logged_at"] = data.get("logged_at") or _now()
    log = WorkoutLog(user_id=user_id, **data)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def list_workout_logs(
    db: Session, user_id: uuid.UUID, start: datetime | None = None, end: datetime | None = None
) -> list[WorkoutLog]:
    stmt = select(WorkoutLog).where(WorkoutLog.user_id == user_id)
    if start is not None:
        stmt = stmt.where(WorkoutLog.logged_at >= start)
    if end is not None:
        stmt = stmt.where(WorkoutLog.logged_at < end)
    return list(db.execute(stmt.order_by(WorkoutLog.logged_at.desc())).scalars())


def _get_owned_workout_log(db: Session, user_id: uuid.UUID, log_id: uuid.UUID) -> WorkoutLog:
    log = db.execute(
        select(WorkoutLog).where(WorkoutLog.id == log_id, WorkoutLog.user_id == user_id)
    ).scalar_one_or_none()
    if log is None:
        raise NotFoundError("Workout log not found")
    return log


def update_workout_log(
    db: Session, user_id: uuid.UUID, log_id: uuid.UUID, payload: WorkoutLogUpdate
) -> WorkoutLog:
    log = _get_owned_workout_log(db, user_id, log_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(log, field, value)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def delete_workout_log(db: Session, user_id: uuid.UUID, log_id: uuid.UUID) -> None:
    log = _get_owned_workout_log(db, user_id, log_id)
    db.delete(log)
    db.commit()


# ---- Mood ----


def create_mood_log(db: Session, user_id: uuid.UUID, payload: MoodLogCreate) -> MoodLog:
    data = payload.model_dump()
    data["logged_at"] = data.get("logged_at") or _now()
    log = MoodLog(user_id=user_id, **data)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def list_mood_logs(
    db: Session, user_id: uuid.UUID, start: datetime | None = None, end: datetime | None = None
) -> list[MoodLog]:
    stmt = select(MoodLog).where(MoodLog.user_id == user_id)
    if start is not None:
        stmt = stmt.where(MoodLog.logged_at >= start)
    if end is not None:
        stmt = stmt.where(MoodLog.logged_at < end)
    return list(db.execute(stmt.order_by(MoodLog.logged_at.desc())).scalars())


def _get_owned_mood_log(db: Session, user_id: uuid.UUID, log_id: uuid.UUID) -> MoodLog:
    log = db.execute(
        select(MoodLog).where(MoodLog.id == log_id, MoodLog.user_id == user_id)
    ).scalar_one_or_none()
    if log is None:
        raise NotFoundError("Mood log not found")
    return log


def delete_mood_log(db: Session, user_id: uuid.UUID, log_id: uuid.UUID) -> None:
    log = _get_owned_mood_log(db, user_id, log_id)
    db.delete(log)
    db.commit()


# ---- Today summary ----


def _get_sleep_log_for_date(db: Session, user_id: uuid.UUID, sleep_date: date) -> SleepLog | None:
    return db.execute(
        select(SleepLog).where(SleepLog.user_id == user_id, SleepLog.sleep_date == sleep_date)
    ).scalar_one_or_none()


def get_today_summary(db: Session, user_id: uuid.UUID, today: date) -> dict:
    """Everything the Home/Today surfaces need in one call. Every number here
    comes straight from stored logs — if nothing was logged, the honest
    answer is an empty list or a None total, never a fabricated figure."""
    day_start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    meals = list_diet_logs(db, user_id, start=day_start, end=day_end)
    water_logs = list_water_logs(db, user_id, start=day_start, end=day_end)
    workouts = list_workout_logs(db, user_id, start=day_start, end=day_end)
    moods_today = list_mood_logs(db, user_id, start=day_start, end=day_end)

    water_total = sum(w.amount_ml for w in water_logs)
    calorie_values = [m.calories for m in meals if m.calories is not None]
    calories_total = sum(calorie_values) if calorie_values else None

    # "Last night's sleep" means exactly that — today's entry if it's already
    # been logged, otherwise yesterday's. Deliberately NOT "most recently
    # logged sleep ever": falling back to a week-old log and presenting it as
    # last night's would be stale data dressed up as current, which is the
    # exact kind of fake-confidence the master doc rules out.
    last_night_sleep = _get_sleep_log_for_date(db, user_id, today) or _get_sleep_log_for_date(
        db, user_id, today - timedelta(days=1)
    )

    return {
        "water_ml_total": water_total,
        "meals_logged": meals,
        "calories_total": calories_total,
        "last_night_sleep": last_night_sleep,
        "workouts_today": workouts,
        # moods_today is already ordered logged_at DESC, so [0] is the latest.
        "latest_mood_today": moods_today[0] if moods_today else None,
    }
