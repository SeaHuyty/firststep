"""FastAPI application factory."""

import logging
import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime

# Silence the library's startup banner; must run before pydantic-ai is
# imported.
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.agent.services import build_services
from app.api.routes import router
from app.audit.log import utc_now
from app.core.settings import Settings, get_settings
from app.llm.adapter import Model, build_model, model_settings

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    clock: Callable[[], datetime] = utc_now,
    model: Model | None = None,
) -> FastAPI:
    """Return the app; tests pass their own settings, clock or model."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.services = build_services(settings, clock)
        built, provider = build_model(settings)
        app.state.model = model or built
        app.state.llm_provider = "test" if model is not None else provider
        app.state.model_settings = model_settings(settings)
        logger.info("FirstStep ready (LLM: %s)", app.state.llm_provider)
        yield

    app = FastAPI(
        title="FirstStep API",
        version="1.0.0",
        description=(
            "A trustworthy first advisor for first-time investors. Educational simulation."
        ),
        lifespan=lifespan,
    )
    app.include_router(router)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        """Return one error string; never echo submitted values."""
        return JSONResponse({"error": "That request didn't look right."}, status_code=422)

    return app
