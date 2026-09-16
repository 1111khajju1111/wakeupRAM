"""
Auth domain service. Route handlers (app/api/v1/endpoints/auth.py) stay thin
and delegate to this module — keeps AI/business logic testable independent
of FastAPI request/response plumbing.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.profile import Profile
from app.models.user import User


class AuthError(Exception):
    """Raised for any auth failure the API layer should turn into a 401/409."""


def register_user(db: Session, email: str, password: str) -> User:
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        raise AuthError("An account with this email already exists.")

    user = User(email=email, hashed_password=hash_password(password))
    db.add(user)
    db.flush()  # get user.id before creating the dependent profile

    # Every user gets a profile row immediately — no downstream code should
    # ever have to handle "user with no profile" as a special case.
    profile = Profile(user_id=user.id)
    db.add(profile)

    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthError("Incorrect email or password.")
    if not user.is_active:
        raise AuthError("This account has been deactivated.")
    return user


def issue_token_pair(user: User) -> tuple[str, str]:
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))
    return access_token, refresh_token
