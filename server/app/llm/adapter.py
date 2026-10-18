"""The only module that knows which LLM provider is used.

`LLM_PROVIDER` picks one: "fake" (scripted, no key, no network; tests,
CI and the offline demo), "openrouter" (a fallback chain of models,
e.g. several free ones), "anthropic" or "google". A missing key falls
back to the fake model with a warning, so the demo never breaks.
"""

import logging

from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider
from pydantic_ai.settings import ModelSettings

from app.core.settings import Settings
from app.llm.fake import fake_model

__all__ = ["Model", "build_model", "model_settings"]

logger = logging.getLogger(__name__)


def _openrouter(settings: Settings) -> Model | None:
    if settings.openrouter_api_key is None or not settings.openrouter_models:
        return None
    provider = OpenRouterProvider(
        api_key=settings.openrouter_api_key.get_secret_value(), app_title="FirstStep"
    )
    models = [OpenRouterModel(name, provider=provider) for name in settings.openrouter_models]
    return models[0] if len(models) == 1 else FallbackModel(models[0], *models[1:])


def _anthropic(settings: Settings) -> Model | None:
    if settings.anthropic_api_key is None:
        return None
    key = settings.anthropic_api_key.get_secret_value()
    return AnthropicModel(settings.anthropic_model, provider=AnthropicProvider(api_key=key))


def _google(settings: Settings) -> Model | None:
    if settings.google_generative_ai_api_key is None:
        return None
    key = settings.google_generative_ai_api_key.get_secret_value()
    provider = GoogleProvider(api_key=key)
    # Comma-separated, like OpenRouter's: the next model answers when
    # one errors (free endpoints give the odd bare 500). May repeat.
    names = [n.strip() for n in settings.gemini_model.split(",") if n.strip()]
    models = [GoogleModel(name, provider=provider) for name in names]
    return models[0] if len(models) == 1 else FallbackModel(models[0], *models[1:])


def build_model(settings: Settings) -> tuple[Model, str]:
    """Return the model to use and the name of its provider."""
    builders = {"openrouter": _openrouter, "anthropic": _anthropic, "google": _google}
    if settings.llm_provider in builders:
        model = builders[settings.llm_provider](settings)
        if model is not None:
            return model, settings.llm_provider
        logger.warning(
            "LLM_PROVIDER=%s has no key or models; using the fake model", settings.llm_provider
        )
    return fake_model(), "fake"


def model_settings(settings: Settings) -> ModelSettings:
    """Return the sampling settings for every turn."""
    return ModelSettings(temperature=settings.llm_temperature)
