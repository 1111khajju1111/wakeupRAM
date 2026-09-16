"""Google Gemini TTS adapter for Wake Up Ram voice calls."""
import base64

import httpx

from app.core.config import get_settings

settings = get_settings()
GOOGLE_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


class TTSUnavailable(RuntimeError):
    pass


def _language_instruction(language: str) -> str:
    if language == "te":
        return "Speak naturally in Telugu. Keep English technical terms only when they are natural in context."
    if language == "mixed":
        return "Speak naturally in Telugu-English code-switching (casual Indian Telugu mixed with English)."
    return "Speak naturally in English with a calm, confident Indian conversational style."


def synthesize(text: str, language: str) -> tuple[bytes, str]:
    """Generate WAV audio from text. API credentials never leave the backend."""
    if not settings.GOOGLE_API_KEY:
        raise TTSUnavailable("GOOGLE_API_KEY is not configured")

    model = settings.TTS_MODEL_NAME.strip() or "gemini-3.1-flash-tts-preview"
    voice = "Kore"
    prompt = (
        "You are the voice of Wake Up Ram, a calm, disciplined and supportive personal companion. "
        "Do not imitate any real person or copyrighted character. "
        f"{_language_instruction(language)} "
        "Speak only the supplied response, with natural pauses and no extra commentary.\n\n"
        f"Response:\n{text.strip()}"
    )

    payload = {
        "model": model,
        "input": prompt,
        "response_format": {"type": "audio", "mime_type": "audio/wav"},
        "generation_config": {"speech_config": [{"voice": voice}]},
    }

    try:
        response = httpx.post(
            GOOGLE_INTERACTIONS_URL,
            headers={
                "x-goog-api-key": settings.GOOGLE_API_KEY,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=45.0,
        )
    except httpx.HTTPError as exc:
        raise TTSUnavailable(f"Google TTS network error: {exc}") from exc

    if response.status_code != 200:
        raise TTSUnavailable(
            f"Google TTS returned {response.status_code}: {response.text[:500]}"
        )

    try:
        body = response.json()
        audio = body["output_audio"]["data"]
        mime_type = body["output_audio"].get("mime_type", "audio/wav")
        return base64.b64decode(audio), mime_type
    except (ValueError, KeyError, TypeError) as exc:
        raise TTSUnavailable(f"Unexpected Google TTS response: {exc}") from exc
