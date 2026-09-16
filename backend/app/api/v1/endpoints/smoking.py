import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.smoking import (
    SmokingEventCreate,
    SmokingEventRead,
    SmokingEventUpdate,
    SmokingSummary,
)
from app.services import smoking_service

router = APIRouter(prefix="/smoking", tags=["smoking"])


@router.get("/summary", response_model=SmokingSummary)
def get_summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SmokingSummary:
    return SmokingSummary(**smoking_service.get_summary(db, current_user.id))


@router.post("/events", response_model=SmokingEventRead, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: SmokingEventCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SmokingEventRead:
    return smoking_service.create_event(db, current_user.id, payload)


@router.get("/events", response_model=list[SmokingEventRead])
def list_events(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SmokingEventRead]:
    return smoking_service.list_events(db, current_user.id, start=start, end=end)


@router.patch("/events/{event_id}", response_model=SmokingEventRead)
def update_event(
    event_id: uuid.UUID,
    payload: SmokingEventUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SmokingEventRead:
    try:
        return smoking_service.update_event(db, current_user.id, event_id, payload)
    except smoking_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    try:
        smoking_service.delete_event(db, current_user.id, event_id)
    except smoking_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
