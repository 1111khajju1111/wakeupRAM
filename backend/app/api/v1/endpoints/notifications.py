import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.notification import (
    NotificationPreferenceRead,
    NotificationPreferenceUpdate,
    NotificationRead,
    NotificationStatusUpdate,
)
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/preferences", response_model=NotificationPreferenceRead)
def get_preferences(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> NotificationPreferenceRead:
    return notification_service.get_preferences(db, current_user.id)


@router.patch("/preferences", response_model=NotificationPreferenceRead)
def update_preferences(
    payload: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationPreferenceRead:
    return notification_service.update_preferences(db, current_user.id, payload)


@router.post("/refresh", response_model=list[NotificationRead])
def refresh_notifications(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[NotificationRead]:
    """Runs the notification engine for the current user right now and
    returns whatever new notifications it generated. In production a
    scheduled job (Phase 13 infra) would call the same
    notification_service.generate_for_user on a cadence; this endpoint lets
    the frontend trigger the identical logic on demand (e.g. on app open)
    until that scheduler exists."""
    return notification_service.generate_for_user(db, current_user.id)


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[NotificationRead]:
    return notification_service.list_notifications(db, current_user.id, status=status_filter)


@router.patch("/{notification_id}", response_model=NotificationRead)
def update_notification_status(
    notification_id: uuid.UUID,
    payload: NotificationStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationRead:
    try:
        return notification_service.update_status(db, current_user.id, notification_id, payload)
    except notification_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except notification_service.InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
