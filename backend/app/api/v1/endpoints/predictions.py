import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.prediction import (
    ModelVersionRead,
    PredictionFeedbackCreate,
    PredictionFeedbackRead,
    PredictionRead,
    SmokingRiskRequest,
)
from app.services import prediction_service

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.post("/smoking-risk", response_model=PredictionRead, status_code=status.HTTP_201_CREATED)
def predict_smoking_risk(
    payload: SmokingRiskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PredictionRead:
    return prediction_service.predict_smoking_risk(
        db, current_user.id, payload.trigger, payload.craving_intensity, payload.stress_level
    )


@router.post("/habit-adherence/{habit_id}", response_model=PredictionRead, status_code=status.HTTP_201_CREATED)
def predict_habit_adherence(
    habit_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PredictionRead:
    try:
        return prediction_service.predict_habit_adherence(db, current_user.id, habit_id, date.today())
    except prediction_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("", response_model=list[PredictionRead])
def list_predictions(
    prediction_type: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PredictionRead]:
    return prediction_service.list_predictions(db, current_user.id, prediction_type=prediction_type)


@router.get("/model-versions", response_model=list[ModelVersionRead])
def list_model_versions(
    prediction_type: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ModelVersionRead]:
    return prediction_service.list_model_versions(db, current_user.id, prediction_type=prediction_type)


@router.post(
    "/{prediction_id}/feedback", response_model=PredictionFeedbackRead, status_code=status.HTTP_201_CREATED
)
def record_feedback(
    prediction_id: uuid.UUID,
    payload: PredictionFeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PredictionFeedbackRead:
    """Records the user's own confirmation of what actually happened.

    For today's two prediction types this is stored for the user's own
    reflection/audit trail — it does NOT currently retrain either model,
    since both already derive their ground truth automatically from
    SmokingEvent/HabitLog. See prediction_service.record_feedback's
    docstring before assuming this endpoint changes future predictions."""
    try:
        return prediction_service.record_feedback(db, current_user.id, prediction_id, payload.actual_outcome)
    except prediction_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except prediction_service.AlreadyGivenFeedbackError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
