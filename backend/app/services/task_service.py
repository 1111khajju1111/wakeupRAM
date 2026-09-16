import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task import Task, TaskLog
from app.schemas.task import TaskCreate, TaskLogCreate, TaskUpdate


class NotFoundError(Exception):
    pass


def _get_owned_task(db: Session, user_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    task = db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user_id)
    ).scalar_one_or_none()
    if task is None:
        raise NotFoundError("Task not found")
    return task


def _clear_existing_mission(db: Session, user_id: uuid.UUID, due_date: date | None) -> None:
    """At most one is_daily_mission=True task per user per day. Setting a new
    one demotes any previous one rather than allowing two 'today's mission'
    tasks to exist at once, which would make the home screen ambiguous."""
    if due_date is None:
        return
    existing = db.execute(
        select(Task).where(
            Task.user_id == user_id, Task.due_date == due_date, Task.is_daily_mission.is_(True)
        )
    ).scalars()
    for task in existing:
        task.is_daily_mission = False
        db.add(task)


def create_task(db: Session, user_id: uuid.UUID, payload: TaskCreate) -> Task:
    data = payload.model_dump()
    if data.get("is_daily_mission"):
        _clear_existing_mission(db, user_id, data.get("due_date"))

    task = Task(user_id=user_id, **data)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def list_tasks(
    db: Session, user_id: uuid.UUID, due_date: date | None = None, status: str | None = None
) -> list[Task]:
    stmt = select(Task).where(Task.user_id == user_id)
    if due_date is not None:
        stmt = stmt.where(Task.due_date == due_date)
    if status is not None:
        stmt = stmt.where(Task.status == status)
    return list(db.execute(stmt.order_by(Task.due_date.asc(), Task.created_at.asc())).scalars())


def get_task(db: Session, user_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    return _get_owned_task(db, user_id, task_id)


def update_task(db: Session, user_id: uuid.UUID, task_id: uuid.UUID, payload: TaskUpdate) -> Task:
    task = _get_owned_task(db, user_id, task_id)
    update_data = payload.model_dump(exclude_unset=True)

    if update_data.get("is_daily_mission"):
        effective_due_date = update_data.get("due_date", task.due_date)
        _clear_existing_mission(db, user_id, effective_due_date)

    for field, value in update_data.items():
        setattr(task, field, value)

    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, user_id: uuid.UUID, task_id: uuid.UUID) -> None:
    task = _get_owned_task(db, user_id, task_id)
    db.delete(task)
    db.commit()


def log_task_action(
    db: Session, user_id: uuid.UUID, task_id: uuid.UUID, payload: TaskLogCreate
) -> Task:
    """Records the action and updates task.status to match, in one transaction
    so the log history and the current status can never disagree."""
    task = _get_owned_task(db, user_id, task_id)

    log = TaskLog(task_id=task.id, user_id=user_id, action=payload.action, notes=payload.notes)
    db.add(log)

    if payload.action == "completed":
        task.status = "completed"
    elif payload.action == "skipped":
        task.status = "skipped"
    # "rescheduled" leaves status untouched; the caller should also PATCH due_date.

    db.add(task)
    db.commit()
    db.refresh(task)
    return task
