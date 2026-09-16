import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.task import TaskCreate, TaskLogCreate, TaskRead, TaskUpdate
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskRead])
def list_tasks(
    due_date: date | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status", pattern="^(pending|completed|skipped)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TaskRead]:
    return task_service.list_tasks(db, current_user.id, due_date=due_date, status=status_filter)


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskRead:
    return task_service.create_task(db, current_user.id, payload)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TaskRead:
    try:
        return task_service.get_task(db, current_user.id, task_id)
    except task_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskRead:
    try:
        return task_service.update_task(db, current_user.id, task_id, payload)
    except task_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    try:
        task_service.delete_task(db, current_user.id, task_id)
    except task_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{task_id}/logs", response_model=TaskRead)
def log_task_action(
    task_id: uuid.UUID,
    payload: TaskLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskRead:
    """Records a completion/skip/reschedule and returns the updated task
    (status reflects the action immediately)."""
    try:
        return task_service.log_task_action(db, current_user.id, task_id, payload)
    except task_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
