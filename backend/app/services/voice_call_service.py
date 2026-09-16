"""
Voice call session service (section 13).

A call is a Conversation (Phase 3's existing model, reused unchanged) plus
a VoiceCall row tracking call-specific state: language, timing, and local
recording metadata. The actual turn-by-turn exchange during a call uses the
existing conversation_service.append_message / ai.ram_core.handle_user_message
pipeline directly — nothing here duplicates that orchestration.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.voice_call import VoiceCall
from app.schemas.voice_call import VoiceCallCreate, VoiceCallEnd
from app.services import conversation_service


class NotFoundError(Exception):
    pass


class AlreadyEndedError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def start_call(db: Session, user_id: uuid.UUID, preferred_language: str, payload: VoiceCallCreate) -> VoiceCall:
    language = payload.language or (preferred_language if preferred_language in ("en", "te") else "mixed")

    # language_override is what actually makes a call's language choice
    # real: without it, ram_core.handle_user_message has no way to know this
    # conversation should use `language` instead of the user's profile
    # default (see the comment there for the bug this fixes).
    conversation = conversation_service.create_conversation(
        db, user_id, mode="adaptive", title=payload.title or "Call", language_override=language
    )

    call = VoiceCall(
        user_id=user_id,
        conversation_id=conversation.id,
        language=language,
        status="in_progress",
        started_at=_now(),
        recording_enabled=payload.recording_enabled,
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    return call


def list_calls(db: Session, user_id: uuid.UUID) -> list[VoiceCall]:
    stmt = select(VoiceCall).where(VoiceCall.user_id == user_id).order_by(VoiceCall.started_at.desc())
    return list(db.execute(stmt).scalars())


def get_owned_call(db: Session, user_id: uuid.UUID, call_id: uuid.UUID) -> VoiceCall:
    call = db.execute(
        select(VoiceCall).where(VoiceCall.id == call_id, VoiceCall.user_id == user_id)
    ).scalar_one_or_none()
    if call is None:
        raise NotFoundError("Call not found")
    return call


def end_call(db: Session, user_id: uuid.UUID, call_id: uuid.UUID, payload: VoiceCallEnd) -> VoiceCall:
    call = get_owned_call(db, user_id, call_id)
    if call.status == "completed":
        raise AlreadyEndedError("Call has already ended")

    now = _now()
    call.status = "completed"
    call.ended_at = now
    # started_at is always tz-aware (set by _now() above at creation), but a
    # row read back from SQLite in tests can come back naive — normalize
    # before subtracting so this doesn't blow up outside Postgres. Same
    # class of bug documented in smoking_service/countdown_service; worth
    # grepping for whenever a new raw datetime comparison against a model
    # field is added.
    started_at = call.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    call.duration_seconds = max(0, int((now - started_at).total_seconds()))

    # Guarded by call.recording_enabled: a client that reports a recording
    # reference for a call that was never started with recording on would
    # otherwise produce a row claiming recording_enabled=False alongside a
    # populated recording_local_reference — an internally inconsistent
    # record of something that, per this call's own settings, shouldn't
    # exist. Silently ignoring it here (not erroring) matches the general
    # "never fabricate, never crash on a harmless mismatch" posture used
    # elsewhere in this service.
    if payload.recording_local_reference is not None and call.recording_enabled:
        call.recording_local_reference = payload.recording_local_reference
    if payload.recording_duration_seconds is not None and call.recording_enabled:
        call.recording_duration_seconds = payload.recording_duration_seconds

    db.add(call)
    db.commit()
    db.refresh(call)
    return call
