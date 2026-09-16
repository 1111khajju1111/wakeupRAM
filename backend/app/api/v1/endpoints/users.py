from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.user import ProfileUpdate, UserRead
from app.services import profile_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> UserRead:
    return current_user


@router.patch("/me/profile", response_model=UserRead)
def update_current_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserRead:
    # profile_service enforces that only the owning user's profile can ever be
    # touched — current_user comes from the verified JWT, never from the body.
    profile_service.update_profile(db, current_user, payload)
    db.refresh(current_user)
    return current_user
