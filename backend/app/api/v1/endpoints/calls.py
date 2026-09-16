import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.voice_call import VoiceCallCreate, VoiceCallEnd, VoiceCallRead
from app.services import voice_call_service

router = APIRouter(prefix="/calls", tags=["calls"])


@router.post("", response_model=VoiceCallRead, status_code=status.HTTP_201_CREATED)
def start_call(
    payload: VoiceCallCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VoiceCallRead:
    preferred_language = current_user.profile.preferred_language if current_user.profile else "en"
    return voice_call_service.start_call(db, current_user.id, preferred_language, payload)


@router.get("", response_model=list[VoiceCallRead])
def list_calls(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[VoiceCallRead]:
    return voice_call_service.list_calls(db, current_user.id)


@router.get("/{call_id}", response_model=VoiceCallRead)
def get_call(
    call_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> VoiceCallRead:
    try:
        return voice_call_service.get_owned_call(db, current_user.id, call_id)
    except voice_call_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{call_id}/end", response_model=VoiceCallRead)
def end_call(
    call_id: uuid.UUID,
    payload: VoiceCallEnd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VoiceCallRead:
    try:
        return voice_call_service.end_call(db, current_user.id, call_id, payload)
    except voice_call_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except voice_call_service.AlreadyEndedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
