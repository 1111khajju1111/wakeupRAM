"""
Import every model here so Alembic's autogenerate and SQLAlchemy's mapper
configuration see the full schema. As later phases add goals/tasks/habits/
health/finance/etc. models, import them below in the same pattern.
"""
from app.models.user import User  # noqa: F401
from app.models.profile import Profile  # noqa: F401
from app.models.goal import Goal  # noqa: F401
from app.models.task import Task, TaskLog  # noqa: F401
from app.models.habit import Habit, HabitLog  # noqa: F401
from app.models.conversation import Conversation, Message  # noqa: F401
from app.models.memory import Memory  # noqa: F401
from app.models.health import DietLog, MoodLog, SleepLog, WaterLog, WorkoutLog  # noqa: F401
from app.models.finance import Budget, Expense, FinancialGoal, Income  # noqa: F401
from app.models.smoking import SmokingEvent  # noqa: F401
from app.models.countdown import Countdown  # noqa: F401
from app.models.notification import Notification, NotificationPreference  # noqa: F401
from app.models.voice_call import VoiceCall  # noqa: F401
from app.models.prediction import ModelFeature, ModelVersion, Prediction, PredictionFeedback  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401

__all__ = [
    "AuditLog",
    "User",
    "Profile",
    "Goal",
    "Task",
    "TaskLog",
    "Habit",
    "HabitLog",
    "Conversation",
    "Message",
    "Memory",
    "DietLog",
    "WaterLog",
    "SleepLog",
    "WorkoutLog",
    "MoodLog",
    "Income",
    "Expense",
    "Budget",
    "FinancialGoal",
    "SmokingEvent",
    "Countdown",
    "Notification",
    "NotificationPreference",
    "VoiceCall",
    "ModelVersion",
    "ModelFeature",
    "Prediction",
    "PredictionFeedback",
]
