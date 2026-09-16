import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.goal import GoalCreate, GoalRead, GoalUpdate
from app.services import goal_service

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_model=list[GoalRead])
def list_goals(
    status_filter: str | None = Query(default=None, alias="status", pattern="^(active|completed|abandoned)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GoalRead]:
    return goal_service.list_goals(db, current_user.id, status=status_filter)


@router.post("", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GoalRead:
    return goal_service.create_goal(db, current_user.id, payload)


@router.get("/{goal_id}", response_model=GoalRead)
def get_goal(
    goal_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> GoalRead:
    try:
        return goal_service.get_goal(db, current_user.id, goal_id)
    except goal_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{goal_id}", response_model=GoalRead)
def update_goal(
    goal_id: uuid.UUID,
    payload: GoalUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GoalRead:
    try:
        return goal_service.update_goal(db, current_user.id, goal_id, payload)
    except goal_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    try:
        goal_service.delete_goal(db, current_user.id, goal_id)
    except goal_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
