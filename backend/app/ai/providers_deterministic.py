"""
Deterministic fallback/test provider.

This is NOT a stand-in for real intelligence — it exists so the conversation
pipeline (storage, memory extraction plumbing, authorization, error paths)
can be exercised in tests and local dev without an GROQ_API_KEY or
network access. Its replies are intentionally plain and say what they are,
never simulate genuine understanding.
"""
from app.ai.provider import AIResponse


class DeterministicProvider:
    def generate(self, *, system_prompt: str, history: list[dict], max_tokens: int) -> AIResponse:
        last_user_message = next(
            (m["content"] for m in reversed(history) if m["role"] == "user"), ""
        )
        reply = (
            "(No AI provider is configured, so this is a placeholder reply — "
            f"you said: \"{last_user_message[:200]}\". Set GROQ_API_KEY to "
            "enable real conversation.)"
        )
        return AIResponse(reply_text=reply, memory_updates=[])
