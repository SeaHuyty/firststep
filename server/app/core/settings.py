"""Settings read from the environment and server/.env."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

SERVER_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Server settings; every field can be set in server/.env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "fake" runs scripted replies with no key and no network: tests, CI
    # and the offline demo use it.
    llm_provider: Literal["fake", "openrouter", "anthropic", "google"] = "fake"
    openrouter_api_key: SecretStr | None = None
    # Tried in order; the next one is used when a model errors or is
    # rate-limited. Only models that support tool calling belong here.
    # Comma-separated in .env: OPENROUTER_MODELS=a:free,b:free
    openrouter_models: Annotated[list[str], NoDecode] = Field(default_factory=list)
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-haiku-5-5"
    google_generative_ai_api_key: SecretStr | None = None
    # One model, or a comma-separated fallback chain like OpenRouter's.
    gemini_model: str = "gemini-3.5-flash-lite"
    llm_temperature: float = 0.2
    # Seconds a typed turn may take, fallbacks included. Keep it under
    # the web proxy's limit (client/next.config.ts); the evidence
    # scripts allow slow free models longer (scripts/harness.py).
    llm_turn_timeout_s: float = 45

    # Signs confirmation tokens. Must be set to a long random value
    # outside local development.
    confirm_secret: SecretStr = SecretStr("dev-only-change-me")

    data_dir: Path = SERVER_DIR / "data"
    db_path: Path = SERVER_DIR / "sandbox.db"
    evidence_dir: Path = SERVER_DIR / "evidence"

    @field_validator("openrouter_models", mode="before")
    @classmethod
    def _split_models(cls, value: object) -> object:
        """Accept a comma-separated string as well as a list."""
        if isinstance(value, str):
            return [m.strip() for m in value.split(",") if m.strip()]
        return value

    @field_validator("openrouter_models", "gemini_model")
    @classmethod
    def _no_key_in_names(cls, value: object) -> object:
        """Refuse a doubled key, as in GEMINI_MODEL=GEMINI_MODEL=a."""
        names = value if isinstance(value, list) else str(value).split(",")
        if any("=" in str(n) for n in names):
            msg = "a model name contains '='; write the .env line once, as NAME=model-a,model-b"
            raise ValueError(msg)
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings object."""
    return Settings()
