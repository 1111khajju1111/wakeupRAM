"""
RAM Core: the orchestration layer between an incoming user message and a
stored assistant reply.

Sequence:
1. Persist the user's message immediately — it must never be lost even if
   everything downstream fails.
2. Retrieve relevant stored memory for context.
3. Build the system prompt (personality + safety + mode + memory context).
4. Call the configured provider.
5. On success: persist the assistant reply, write back any proposed memory
   updates as INFERRED/conversation_extracted (never as user_stated).
6. On provider outage: persist a clearly-labeled fallback assistant message
   instead of crashing the conversation or silently losing the exchange.
"""
import uuid

from sqlalchemy.orm import Session

from app.ai.personality import build_memory_context, build_system_prompt
from app.ai.provider import AIProvider, AIProviderUnavailable
from app.ai.providers_deterministic import DeterministicProvider
from app.ai.providers_groq import GroqProvider
from app.core.config import get_settings
from app.models.conversation import Message
from app.services import conversation_service, memory_service

settings = get_settings()

FALLBACK_MESSAGE = (
    "I couldn't reach the AI service just now, so I can't respond properly to "
    "that yet. Your message is saved — try again in a moment."
)


def get_provider() -> AIProvider:
    """Return the configured AI provider. Wake Up Ram uses Groq as its real AI provider."""
    provider_name = settings.AI_PROVIDER.strip().lower()
    api_key = settings.GROQ_API_KEY.strip()

    if provider_name == "groq" and api_key:
        return GroqProvider(api_key=api_key, model_name=settings.AI_MODEL_NAME)

    # Never fabricate an AI response when Groq is unavailable or unconfigured.
    # DeterministicProvider is the explicit degraded-mode provider used for local testing.
    return DeterministicProvider()


def handle_user_message(
    db: Session,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user_message_content: str,
    preferred_language: str,
) -> tuple[Message, Message]:
    conversation = conversation_service.get_owned_conversation(db, user_id, conversation_id)

    user_message = conversation_service.append_message(
        db, user_id, conversation_id, role="user", content=user_message_content
    )

    # `preferred_language` (the caller's argument) is the user's standing
    # Profile default — but a conversation created with its own
    # language_override (currently: voice calls, see
    # voice_call_service.start_call) must win over that default. Without
    # this, a call explicitly started in a language different from the
    # profile default silently generated replies in the profile's language
    # instead — the override was stored on the row but never actually read
    # by anything that generates a response.
    #
    # build_system_prompt only distinguishes "te" (natural Telugu, with
    # code-switching to English for technical terms) from everything else.
    # "mixed" maps onto that same "te" branch because the instruction
    # already IS a code-switching instruction — a separate branch for
    # "mixed" would ask for identical behavior through different wording.
    effective_language = conversation.language_override or preferred_language
    prompt_language = "te" if effective_language in ("te", "mixed") else "en"

    memories = memory_service.retrieve_for_prompt(db, user_id, settings.AI_MEMORY_RETRIEVAL_LIMIT)
    memory_context = build_memory_context(memories)
    system_prompt = build_system_prompt(
        mode=conversation.mode, preferred_language=prompt_language, memory_context=memory_context
    )

    history_messages = conversation_service.list_messages(db, user_id, conversation_id)
    history = [{"role": m.role, "content": m.content} for m in history_messages]

    provider = get_provider()

    try:
        ai_response = provider.generate(
            system_prompt=system_prompt, history=history, max_tokens=settings.AI_MAX_TOKENS
        )
    except AIProviderUnavailable:
        assistant_message = conversation_service.append_message(
            db, user_id, conversation_id, role="assistant", content=FALLBACK_MESSAGE, is_fallback=True
        )
        return user_message, assistant_message

    assistant_message = conversation_service.append_message(
        db, user_id, conversation_id, role="assistant", content=ai_response.reply_text
    )

    for update in ai_response.memory_updates:
        category = update.get("category")
        content = update.get("content")
        confidence = update.get("confidence", 0.6)
        if not category or not content:
            continue  # malformed candidate — skip rather than fail the whole turn
        memory_service.store_extracted_memory(db, user_id, category, content, confidence)

    return user_message, assistant_message
