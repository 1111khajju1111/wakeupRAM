from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.habit import HabitWithStreak
from app.schemas.today import TodayView
from app.services import countdown_service, goal_service, habit_service, task_service

router = APIRouter(prefix="/today", tags=["today"])


@router.get("", response_model=TodayView)
def get_today(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TodayView:
    today = date.today()

    todays_tasks = task_service.list_tasks(db, current_user.id, due_date=today)
    mission = next((t for t in todays_tasks if t.is_daily_mission), None)

    all_habits = habit_service.list_habits(db, current_user.id, active_only=True)
    due_today = [h for h in all_habits if habit_service.is_due_today(h, today)]
    habits_with_streak = [
        HabitWithStreak(
            id=h.id,
            title=h.title,
            frequency=h.frequency,
            repeat_days=h.repeat_days,
            target_count_per_period=h.target_count_per_period,
            active=h.active,
            created_at=h.created_at,
            updated_at=h.updated_at,
            current_streak=habit_service.calculate_current_streak(db, h, today),
            completed_today=any(log.completed_on == today for log in h.logs),
        )
        for h in due_today
    ]

    active_goals_count = len(goal_service.list_goals(db, current_user.id, status="active"))
    active_countdown = countdown_service.get_next_active_countdown(db, current_user.id)

    return TodayView(
        mission=mission,
        habits_due_today=habits_with_streak,
        active_goals_count=active_goals_count,
        active_countdown=active_countdown,
    )
