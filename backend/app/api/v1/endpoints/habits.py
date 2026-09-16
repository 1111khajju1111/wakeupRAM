import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.habit import (
    HabitCreate,
    HabitLogCreate,
    HabitLogRead,
    HabitUpdate,
    HabitWithStreak,
)
from app.services import habit_service

router = APIRouter(prefix="/habits", tags=["habits"])


def _to_with_streak(db: Session, habit, today: date) -> HabitWithStreak:
    streak = habit_service.calculate_current_streak(db, habit, today)
    completed_today = any(log.completed_on == today for log in habit.logs)
    return HabitWithStreak(
        id=habit.id,
        title=habit.title,
        frequency=habit.frequency,
        repeat_days=habit.repeat_days,
        target_count_per_period=habit.target_count_per_period,
        active=habit.active,
        created_at=habit.created_at,
        updated_at=habit.updated_at,
        current_streak=streak,
        completed_today=completed_today,
    )


@router.get("", response_model=list[HabitWithStreak])
def list_habits(
    active_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[HabitWithStreak]:
    today = date.today()
    habits = habit_service.list_habits(db, current_user.id, active_only=active_only)
    return [_to_with_streak(db, habit, today) for habit in habits]


@router.post("", response_model=HabitWithStreak, status_code=status.HTTP_201_CREATED)
def create_habit(
    payload: HabitCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HabitWithStreak:
    habit = habit_service.create_habit(db, current_user.id, payload)
    return _to_with_streak(db, habit, date.today())


@router.patch("/{habit_id}", response_model=HabitWithStreak)
def update_habit(
    habit_id: uuid.UUID,
    payload: HabitUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HabitWithStreak:
    try:
        habit = habit_service.update_habit(db, current_user.id, habit_id, payload)
    except habit_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_with_streak(db, habit, date.today())


@router.delete("/{habit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_habit(
    habit_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    try:
        habit_service.delete_habit(db, current_user.id, habit_id)
    except habit_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{habit_id}/logs", response_model=HabitLogRead, status_code=status.HTTP_201_CREATED)
def log_habit(
    habit_id: uuid.UUID,
    payload: HabitLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HabitLogRead:
    try:
        return habit_service.log_habit_completion(db, current_user.id, habit_id, payload)
    except habit_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
