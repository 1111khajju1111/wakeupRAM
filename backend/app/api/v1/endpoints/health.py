import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.health import (
    DietLogCreate,
    DietLogRead,
    DietLogUpdate,
    HealthTodaySummary,
    MoodLogCreate,
    MoodLogRead,
    SleepLogCreate,
    SleepLogRead,
    SleepLogUpdate,
    WaterLogCreate,
    WaterLogRead,
    WorkoutLogCreate,
    WorkoutLogRead,
    WorkoutLogUpdate,
)
from app.services import health_service

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/today", response_model=HealthTodaySummary)
def get_today_summary(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> HealthTodaySummary:
    return HealthTodaySummary(**health_service.get_today_summary(db, current_user.id, date.today()))


# ---- Diet ----


@router.post("/diet", response_model=DietLogRead, status_code=status.HTTP_201_CREATED)
def create_diet_log(
    payload: DietLogCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DietLogRead:
    return health_service.create_diet_log(db, current_user.id, payload)


@router.get("/diet", response_model=list[DietLogRead])
def list_diet_logs(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DietLogRead]:
    return health_service.list_diet_logs(db, current_user.id, start=start, end=end)


@router.patch("/diet/{log_id}", response_model=DietLogRead)
def update_diet_log(
    log_id: uuid.UUID,
    payload: DietLogUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DietLogRead:
    try:
        return health_service.update_diet_log(db, current_user.id, log_id, payload)
    except health_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/diet/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_diet_log(
    log_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    try:
        health_service.delete_diet_log(db, current_user.id, log_id)
    except health_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---- Water ----


@router.post("/water", response_model=WaterLogRead, status_code=status.HTTP_201_CREATED)
def create_water_log(
    payload: WaterLogCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> WaterLogRead:
    return health_service.create_water_log(db, current_user.id, payload)


@router.get("/water", response_model=list[WaterLogRead])
def list_water_logs(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WaterLogRead]:
    return health_service.list_water_logs(db, current_user.id, start=start, end=end)


@router.delete("/water/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_water_log(
    log_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    try:
        health_service.delete_water_log(db, current_user.id, log_id)
    except health_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---- Sleep ----


@router.post("/sleep", response_model=SleepLogRead, status_code=status.HTTP_200_OK)
def log_sleep(
    payload: SleepLogCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SleepLogRead:
    """200, not 201: this is an upsert keyed on sleep_date, so a repeat call
    for the same night updates the existing row rather than creating one."""
    return health_service.log_sleep(db, current_user.id, payload)


@router.get("/sleep", response_model=list[SleepLogRead])
def list_sleep_logs(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SleepLogRead]:
    return health_service.list_sleep_logs(db, current_user.id, start=start, end=end)


@router.patch("/sleep/{log_id}", response_model=SleepLogRead)
def update_sleep_log(
    log_id: uuid.UUID,
    payload: SleepLogUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SleepLogRead:
    try:
        return health_service.update_sleep_log(db, current_user.id, log_id, payload)
    except health_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/sleep/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sleep_log(
    log_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    try:
        health_service.delete_sleep_log(db, current_user.id, log_id)
    except health_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---- Workout ----


@router.post("/workouts", response_model=WorkoutLogRead, status_code=status.HTTP_201_CREATED)
def create_workout_log(
    payload: WorkoutLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkoutLogRead:
    return health_service.create_workout_log(db, current_user.id, payload)


@router.get("/workouts", response_model=list[WorkoutLogRead])
def list_workout_logs(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WorkoutLogRead]:
    return health_service.list_workout_logs(db, current_user.id, start=start, end=end)


@router.patch("/workouts/{log_id}", response_model=WorkoutLogRead)
def update_workout_log(
    log_id: uuid.UUID,
    payload: WorkoutLogUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkoutLogRead:
    try:
        return health_service.update_workout_log(db, current_user.id, log_id, payload)
    except health_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/workouts/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workout_log(
    log_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    try:
        health_service.delete_workout_log(db, current_user.id, log_id)
    except health_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---- Mood ----


@router.post("/mood", response_model=MoodLogRead, status_code=status.HTTP_201_CREATED)
def create_mood_log(
    payload: MoodLogCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> MoodLogRead:
    return health_service.create_mood_log(db, current_user.id, payload)


@router.get("/mood", response_model=list[MoodLogRead])
def list_mood_logs(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MoodLogRead]:
    return health_service.list_mood_logs(db, current_user.id, start=start, end=end)


@router.delete("/mood/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mood_log(
    log_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    try:
        health_service.delete_mood_log(db, current_user.id, log_id)
    except health_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
