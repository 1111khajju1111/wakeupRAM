import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.countdown import CountdownCreate, CountdownRead, CountdownUpdate
from app.services import countdown_service

router = APIRouter(prefix="/countdowns", tags=["countdowns"])


@router.post("", response_model=CountdownRead, status_code=status.HTTP_201_CREATED)
def create_countdown(
    payload: CountdownCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CountdownRead:
    return countdown_service.create_countdown(db, current_user.id, payload)


@router.get("", response_model=list[CountdownRead])
def list_countdowns(
    active_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CountdownRead]:
    return countdown_service.list_countdowns(db, current_user.id, active_only=active_only)


@router.get("/{countdown_id}", response_model=CountdownRead)
def get_countdown(
    countdown_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CountdownRead:
    try:
        return countdown_service.get_countdown(db, current_user.id, countdown_id)
    except countdown_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{countdown_id}", response_model=CountdownRead)
def update_countdown(
    countdown_id: uuid.UUID,
    payload: CountdownUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CountdownRead:
    try:
        return countdown_service.update_countdown(db, current_user.id, countdown_id, payload)
    except countdown_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{countdown_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_countdown(
    countdown_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    try:
        countdown_service.delete_countdown(db, current_user.id, countdown_id)
    except countdown_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
