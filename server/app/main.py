import os

# Silence the library's startup banner; must run before pydantic-ai
# is imported.
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.market.service import MarketService, fetch_stocks
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start the background market loads when the app starts."""
    if get_settings().market_enabled:
        # The S&P 500 screen takes about a minute, so it always loads in
        # the background.
        app.state.stocks.kick()
        # Warm the cache so the first page view has live data.
        app.state.market.kick()
    yield


app = FastAPI(title="WealthPilot AI server", version="0.1.0", lifespan=lifespan)
app.state.market = MarketService(ttl=get_settings().market_ttl_seconds)
# Whole-universe price history, for the stock screen.
app.state.stocks = MarketService(fetcher=fetch_stocks, ttl=6 * 3600)
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Return one error string, never echoing the submitted values."""
    return JSONResponse({"error": "Invalid request"}, status_code=422)
