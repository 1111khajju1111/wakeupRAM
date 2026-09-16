"""
Provider interface for whatever LLM actually generates Ram's replies.

Every concrete provider must:
1. Accept a system prompt + message history and return an AIResponse.
2. Never raise for "the model declined" or "the JSON was malformed" — those
   are handled internally and folded into a best-effort AIResponse. Only
   raise AIProviderUnavailable for things ram_core.py should treat as a full
   outage (auth failure, network error, timeout) so it can fail gracefully.
"""
from dataclasses import dataclass, field
from typing import Protocol

import json


@dataclass
class AIResponse:
    reply_text: str
    # Candidate memories the model proposed extracting from this exchange.
    # Each dict: {"category": str, "content": str, "confidence": float}.
    # ram_core.py treats these as inferred/extracted, never as user_stated.
    memory_updates: list[dict] = field(default_factory=list)
    used_fallback_parsing: bool = False


class AIProviderUnavailable(Exception):
    """Raised when the provider genuinely could not be reached — auth
    failure, network error, timeout. NOT raised for a well-formed but
    unparseable response; that's handled as a degraded AIResponse instead."""


class AIProvider(Protocol):
    def generate(
        self,
        *,
        system_prompt: str,
        history: list[dict],  # [{"role": "user"|"assistant", "content": str}, ...]
        max_tokens: int,
    ) -> AIResponse: ...


# Shared JSON-envelope contract for every real (non-deterministic) provider.
# Ram is instructed to respond with a strict JSON object so the backend can
# separate the conversational reply from structured memory-extraction
# candidates in a single round trip, rather than doubling API calls. Every
# real provider appends this to its system prompt and parses the response
# the same way (parse_json_envelope_response below) — one shared contract,
# not a per-provider reimplementation that could quietly drift.
RESPONSE_FORMAT_INSTRUCTIONS = """
Respond with a single JSON object and nothing else — no markdown fences, no
commentary before or after it. Shape:

{
  "reply": "<what you say to the user, in their preferred language>",
  "memory_updates": [
    {"category": "fact|preference|goal_context|habit_context|lesson|behavior_pattern|context",
     "content": "<a single, specific, durable statement>",
     "confidence": <0.0-1.0>}
  ]
}

Only include a memory_update for something durable and specific the user
revealed this turn — not your own reasoning, not restating what they already
have stored, not speculation. If nothing durable came up, use an empty list.
""".strip()


def parse_json_envelope_response(raw_text: str) -> AIResponse:
    """Shared parse path for any provider using RESPONSE_FORMAT_INSTRUCTIONS.
    A model may still wrap JSON in a code fence despite instructions — strip
    that defensively before attempting to parse. A parsing failure must
    never surface as a broken conversation, so the degraded path treats the
    raw text as the reply and extracts zero memories rather than raising."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

    try:
        parsed = json.loads(cleaned)
        reply_text = parsed.get("reply", "").strip()
        memory_updates = parsed.get("memory_updates", [])
        if reply_text:
            return AIResponse(reply_text=reply_text, memory_updates=memory_updates)
    except (json.JSONDecodeError, AttributeError):
        pass

    return AIResponse(
        reply_text=raw_text or "I'm having trouble forming a reply right now.",
        memory_updates=[],
        used_fallback_parsing=True,
    )
