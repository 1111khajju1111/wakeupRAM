from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import ProfileUpdate


def update_profile(db: Session, user: User, payload: ProfileUpdate) -> None:
    """
    Applies only the fields the client actually sent (partial update).
    `user` is always the authenticated caller — there is no code path here
    that accepts a user_id from the request body, which is what guarantees
    a user can never modify someone else's profile.
    """
    profile = user.profile
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(profile, field, value)

    db.add(profile)
    db.commit()
