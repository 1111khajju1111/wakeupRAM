from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    calls,
    conversations,
    countdowns,
    finance,
    goals,
    habits,
    health,
    memories,
    notifications,
    predictions,
    smoking,
    tasks,
    today,
    users,
    voice,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(goals.router)
api_router.include_router(tasks.router)
api_router.include_router(habits.router)
api_router.include_router(today.router)
api_router.include_router(conversations.router)
api_router.include_router(memories.router)
api_router.include_router(health.router)
api_router.include_router(finance.router)
api_router.include_router(smoking.router)
api_router.include_router(countdowns.router)
api_router.include_router(notifications.router)
api_router.include_router(calls.router)
api_router.include_router(predictions.router)
api_router.include_router(voice.router)

# Phase 11+ will add, in this same pattern:
# Phase 11: Capacitor Android + permissions + local storage
# Phase 12: native countdown widget
# Phase 13: security hardening + tests + deployment
