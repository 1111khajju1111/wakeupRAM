import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Section 13: voice should feel like an in-app phone call, not a chat
# screen. The actual conversation turns (transcribed user speech -> RAM
# Core -> AI reply) reuse the existing Conversation/Message pipeline from
# Phase 3 unchanged (conversation_service.append_message,
# ai.ram_core.handle_user_message) — a call is just a Conversation with a
# VoiceCall session wrapped around it for call-specific concerns: start/end
# timestamps, duration, which language the call used, and local recording
# metadata. This keeps AI orchestration in one place rather than forking it
# for voice, per section 20's "keep AI orchestration separate from HTTP
# route handlers" and the master prompt's "do not duplicate."
#
# Speech-to-text and text-to-speech themselves happen entirely client-side
# (the browser/WebView's built-in SpeechRecognition/SpeechSynthesis APIs —
# see frontend/src/services/speech.ts) rather than through a backend
# provider. Unlike the configured text-generation provider, there is no
# credentialed STT/TTS backend integration to abstract here: nothing this
# app can call requires an API key for STT/TTS, so "the real adapter" IS
# the browser platform API, and "the deterministic local/test adapter" is
# speech.ts's manual-text-input fallback when that API isn't available.
# That split lives entirely in the frontend; the backend only ever sees the
# resulting transcript text (as an ordinary message) and never receives or
# stores raw audio bytes — consistent with "local device storage by
# default... no automatic cloud upload" (section 13).


class VoiceCall(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "voice_calls"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # en | te | mixed — mixed means the user's profile preference was
    # "mixed" or the call otherwise wasn't pinned to a single recognition
    # language; see speech.ts for how this maps to SpeechRecognition's lang.
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)

    # in_progress | completed — a call left in_progress (e.g. the app was
    # killed mid-call) is still an honest record of what happened, never
    # silently deleted or force-completed.
    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Recording is user-controlled per call and always local-first (section
    # 13): the backend never receives or stores the audio itself, only
    # whether the user chose to record and — once they end the call — the
    # on-device reference the client reports back, so call history can show
    # "a recording exists for this call" without this app ever handling the
    # raw file.
    recording_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Client-reported local file reference matching the suggested structure
    # in section 13 (Wake Up Ram/Calls/YYYY-MM-DD/HH-MM-SS.<ext>). Never a
    # server path, a URL, or anything this backend can fetch — see the
    # frontend recording note in speech.ts for why the real browser/PWA
    # extension differs slightly from the .m4a the doc suggests (that
    # exact container needs native Android `MediaRecorder`, which lands in
    # Phase 11's Capacitor work).
    recording_local_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recording_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<VoiceCall id={self.id} status={self.status} conversation_id={self.conversation_id}>"
