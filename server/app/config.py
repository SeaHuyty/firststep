from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Pick ONE provider. Claude wins if both are set. Gemini has a free tier.
    google_generative_ai_api_key: str | None = None
    anthropic_api_key: str | None = None

    gemini_model: str = "gemini-3.8-flash"
    gemini_chat_model: str = "gemini-3.5-flash-lite"
    anthropic_model: str = "claude-sonnet-5-5"
    anthropic_chat_model: str = "claude-haiku-5-5"


@lru_cache
def get_settings() -> Settings:
    return Settings()
