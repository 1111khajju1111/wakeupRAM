"""
Real production provider: calls Groq's OpenAI-compatible chat completions
API (https://api.groq.com/openai/v1/chat/completions).

Uses the same shared JSON-envelope contract as the shared provider contract — see
app.ai.provider's RESPONSE_FORMAT_INSTRUCTIONS / parse_json_envelope_response
— so ram_core.py doesn't need to know or care which real provider is
configured; it returns the shared AIResponse shape.
"""
import httpx

from app.ai.provider import (
    RESPONSE_FORMAT_INSTRUCTIONS,
    AIProviderUnavailable,
    AIResponse,
    parse_json_envelope_response,
)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider:
    def __init__(self, api_key: str, model_name: str, timeout_seconds: float = 30.0):
        self._api_key = api_key
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds

    def generate(self, *, system_prompt: str, history: list[dict], max_tokens: int) -> AIResponse:
        full_system_prompt = f"{system_prompt}\n\n{RESPONSE_FORMAT_INSTRUCTIONS}"
        messages = [{"role": "system", "content": full_system_prompt}, *history]

        try:
            response = httpx.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": self._model_name,
                    "max_tokens": max_tokens,
                    "messages": messages,
                },
                timeout=self._timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise AIProviderUnavailable(f"Network error calling Groq API: {exc}") from exc

        if response.status_code != 200:
            raise AIProviderUnavailable(f"Groq API returned {response.status_code}: {response.text[:500]}")

        body = response.json()
        try:
            raw_text = body["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, AttributeError) as exc:
            raise AIProviderUnavailable(f"Unexpected Groq response shape: {exc}") from exc

        return parse_json_envelope_response(raw_text)
