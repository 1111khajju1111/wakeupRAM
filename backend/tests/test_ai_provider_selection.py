"""Unit tests for Groq provider selection."""
from app.ai import ram_core
from app.ai.providers_groq import GroqProvider
from app.ai.providers_deterministic import DeterministicProvider

def _set(monkeypatch, provider: str, api_key: str):
    monkeypatch.setattr(ram_core.settings, "AI_PROVIDER", provider)
    monkeypatch.setattr(ram_core.settings, "GROQ_API_KEY", api_key)

def test_groq_selected_when_provider_is_groq_and_key_present(monkeypatch):
    _set(monkeypatch, "groq", "gsk-test-key")
    assert isinstance(ram_core.get_provider(), GroqProvider)

def test_falls_back_to_deterministic_when_key_missing(monkeypatch):
    _set(monkeypatch, "groq", "")
    assert isinstance(ram_core.get_provider(), DeterministicProvider)

def test_falls_back_to_deterministic_for_unrecognized_provider(monkeypatch):
    _set(monkeypatch, "some_future_provider", "a-key")
    assert isinstance(ram_core.get_provider(), DeterministicProvider)

def test_groq_provider_uses_configured_model_name(monkeypatch):
    _set(monkeypatch, "groq", "gsk-test-key")
    monkeypatch.setattr(ram_core.settings, "AI_MODEL_NAME", "openai/gpt-oss-120b")
    provider = ram_core.get_provider()
    assert isinstance(provider, GroqProvider)
    assert provider._model_name == "openai/gpt-oss-120b"
