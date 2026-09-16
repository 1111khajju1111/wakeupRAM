from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.services.tts_service import TTSUnavailable, synthesize

router = APIRouter(prefix="/voice", tags=["voice"])


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=6000)
    language: str = Field(default="en", pattern="^(en|te|mixed)$")


@router.post("/tts")
def text_to_speech(
    payload: TTSRequest,
    current_user: User = Depends(get_current_user),
) -> Response:
    # Authentication is deliberately required even though the endpoint is
    # stateless. This prevents anonymous use of the paid Google credential.
    del current_user
    try:
        audio, mime_type = synthesize(payload.text, payload.language)
    except TTSUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return Response(
        content=audio,
        media_type=mime_type,
        headers={"Cache-Control": "no-store"},
    )
