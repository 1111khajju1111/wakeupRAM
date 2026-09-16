from pydantic import BaseModel

from app.schemas.countdown import CountdownRead
from app.schemas.habit import HabitWithStreak
from app.schemas.task import TaskRead


class TodayView(BaseModel):
    mission: TaskRead | None
    habits_due_today: list[HabitWithStreak]
    active_goals_count: int
    active_countdown: CountdownRead | None
