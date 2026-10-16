"""Choose the LLM provider and model from the settings."""

from typing import Literal

from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.settings import ModelSettings

from app.config import Settings


def pick_model(settings: Settings, kind: Literal["chat", "explain"]) -> Model | None:
    """Return the model to use, or None for the canned fallback.

    Claude if ANTHROPIC_API_KEY is set, else the Gemini free tier, else
    None. "chat" turns need low latency, so they prefer lite models;
    "explain" prefers quality. On Gemini each falls back to the other's
    model if the first errors (free-tier quotas are per model).
    """
    if settings.anthropic_api_key:
        name = settings.anthropic_chat_model if kind == "chat" else settings.anthropic_model
        return AnthropicModel(name, provider=AnthropicProvider(api_key=settings.anthropic_api_key))

    if settings.google_generative_ai_api_key:
        provider = GoogleProvider(api_key=settings.google_generative_ai_api_key)
        # Our tasks (explaining, extracting facts) need no deep
        # reasoning, and chat runs several model calls per turn on a
        # lite model, so keep thinking low.
        quality = GoogleModel(
            settings.gemini_model, provider=provider, settings=ModelSettings(thinking="low")
        )
        fast = GoogleModel(
            settings.gemini_chat_model,
            provider=provider,
            settings=ModelSettings(thinking="minimal"),
        )
        return FallbackModel(fast, quality) if kind == "chat" else FallbackModel(quality, fast)

    return None
