import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.goal import Goal
from app.schemas.goal import GoalCreate, GoalUpdate


class NotFoundError(Exception):
    pass


def create_goal(db: Session, user_id: uuid.UUID, payload: GoalCreate) -> Goal:
    goal = Goal(user_id=user_id, **payload.model_dump())
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def list_goals(db: Session, user_id: uuid.UUID, status: str | None = None) -> list[Goal]:
    stmt = select(Goal).where(Goal.user_id == user_id)
    if status:
        stmt = stmt.where(Goal.status == status)
    return list(db.execute(stmt.order_by(Goal.created_at.desc())).scalars())


def _get_owned_goal(db: Session, user_id: uuid.UUID, goal_id: uuid.UUID) -> Goal:
    # The WHERE clause includes user_id, not just id — this is what prevents
    # user A from ever reading/editing/deleting user B's goal by guessing an ID.
    goal = db.execute(
        select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
    ).scalar_one_or_none()
    if goal is None:
        raise NotFoundError("Goal not found")
    return goal


def get_goal(db: Session, user_id: uuid.UUID, goal_id: uuid.UUID) -> Goal:
    return _get_owned_goal(db, user_id, goal_id)


def update_goal(db: Session, user_id: uuid.UUID, goal_id: uuid.UUID, payload: GoalUpdate) -> Goal:
    goal = _get_owned_goal(db, user_id, goal_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def delete_goal(db: Session, user_id: uuid.UUID, goal_id: uuid.UUID) -> None:
    goal = _get_owned_goal(db, user_id, goal_id)
    db.delete(goal)
    db.commit()
