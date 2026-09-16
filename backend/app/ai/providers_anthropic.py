"""
Real production provider: calls the Anthropic Messages API directly.

Uses the shared JSON-envelope contract from app.ai.provider — see
RESPONSE_FORMAT_INSTRUCTIONS / parse_json_envelope_response there for the
reply/memory_updates parsing shared with every other real provider (e.g.
providers_groq.py).
"""
import httpx

from app.ai.provider import (
    RESPONSE_FORMAT_INSTRUCTIONS,
    AIProviderUnavailable,
    AIResponse,
    parse_json_envelope_response,
)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"


class AnthropicProvider:
    def __init__(self, api_key: str, model_name: str, timeout_seconds: float = 30.0):
        self._api_key = api_key
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds

    def generate(self, *, system_prompt: str, history: list[dict], max_tokens: int) -> AIResponse:
        full_system_prompt = f"{system_prompt}\n\n{RESPONSE_FORMAT_INSTRUCTIONS}"

        try:
            response = httpx.post(
                ANTHROPIC_API_URL,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": ANTHROPIC_API_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": self._model_name,
                    "max_tokens": max_tokens,
                    "system": full_system_prompt,
                    "messages": history,
                },
                timeout=self._timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise AIProviderUnavailable(f"Network error calling Anthropic API: {exc}") from exc

        if response.status_code != 200:
            raise AIProviderUnavailable(
                f"Anthropic API returned {response.status_code}: {response.text[:500]}"
            )

        body = response.json()
        text_blocks = [block["text"] for block in body.get("content", []) if block.get("type") == "text"]
        raw_text = "\n".join(text_blocks).strip()

        return parse_json_envelope_response(raw_text)
