import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.habit import Habit, HabitLog
from app.schemas.habit import HabitCreate, HabitLogCreate, HabitUpdate


class NotFoundError(Exception):
    pass


def _get_owned_habit(db: Session, user_id: uuid.UUID, habit_id: uuid.UUID) -> Habit:
    habit = db.execute(
        select(Habit).where(Habit.id == habit_id, Habit.user_id == user_id)
    ).scalar_one_or_none()
    if habit is None:
        raise NotFoundError("Habit not found")
    return habit


def create_habit(db: Session, user_id: uuid.UUID, payload: HabitCreate) -> Habit:
    habit = Habit(user_id=user_id, **payload.model_dump())
    db.add(habit)
    db.commit()
    db.refresh(habit)
    return habit


def list_habits(db: Session, user_id: uuid.UUID, active_only: bool = False) -> list[Habit]:
    stmt = select(Habit).where(Habit.user_id == user_id)
    if active_only:
        stmt = stmt.where(Habit.active.is_(True))
    return list(db.execute(stmt.order_by(Habit.created_at.asc())).scalars())


def get_habit(db: Session, user_id: uuid.UUID, habit_id: uuid.UUID) -> Habit:
    return _get_owned_habit(db, user_id, habit_id)


def update_habit(db: Session, user_id: uuid.UUID, habit_id: uuid.UUID, payload: HabitUpdate) -> Habit:
    habit = _get_owned_habit(db, user_id, habit_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(habit, field, value)
    db.add(habit)
    db.commit()
    db.refresh(habit)
    return habit


def delete_habit(db: Session, user_id: uuid.UUID, habit_id: uuid.UUID) -> None:
    habit = _get_owned_habit(db, user_id, habit_id)
    db.delete(habit)
    db.commit()


def log_habit_completion(
    db: Session, user_id: uuid.UUID, habit_id: uuid.UUID, payload: HabitLogCreate
) -> HabitLog:
    habit = _get_owned_habit(db, user_id, habit_id)
    completed_on = payload.completed_on or date.today()

    # Idempotent: logging the same day twice updates the note rather than
    # creating a duplicate completion, so a double-tap can't inflate a streak.
    existing = db.execute(
        select(HabitLog).where(HabitLog.habit_id == habit.id, HabitLog.completed_on == completed_on)
    ).scalar_one_or_none()

    if existing:
        existing.notes = payload.notes
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    log = HabitLog(habit_id=habit.id, user_id=user_id, completed_on=completed_on, notes=payload.notes)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def is_due_today(habit: Habit, today: date) -> bool:
    if habit.frequency == "daily":
        return True
    if habit.frequency == "weekly":
        if not habit.repeat_days:
            return False
        # Python's date.weekday(): Mon=0..Sun=6. Convert to the model's
        # Sun=0..Sat=6 convention used in repeat_days.
        sunday_indexed = (today.weekday() + 1) % 7
        return sunday_indexed in habit.repeat_days
    return False


def calculate_current_streak(db: Session, habit: Habit, today: date) -> int:
    """Counts consecutive due-days (working backward from today) that have a
    completion log. Stops at the first due-day with no log."""
    logged_dates = set(
        db.execute(select(HabitLog.completed_on).where(HabitLog.habit_id == habit.id)).scalars()
    )

    streak = 0
    cursor = today
    # Cap the walk-back at a year so an old, rarely-due weekly habit can't
    # cause an unbounded loop.
    for _ in range(366):
        if is_due_today(habit, cursor):
            if cursor in logged_dates:
                streak += 1
            else:
                break
        cursor -= timedelta(days=1)

    return streak
