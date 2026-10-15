import os

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")  # silence the library's startup banner

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.market.service import MarketService
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().market_enabled:
        app.state.market.kick()  # warm the cache in the background so the first page view has live data
    yield


app = FastAPI(title="WealthPilot AI server", version="0.1.0", lifespan=lifespan)
app.state.market = MarketService(ttl=get_settings().market_ttl_seconds)
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_error(_, exc: RequestValidationError):
    # Keep the client contract simple: one error string, no echoing of submitted values.
    return JSONResponse({"error": "Invalid request"}, status_code=422)
