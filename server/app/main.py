import os

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")  # silence the library's startup banner

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.routes import router

app = FastAPI(title="WealthPilot AI server", version="0.1.0")
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_error(_, exc: RequestValidationError):
    # Keep the client contract simple: one error string, no echoing of submitted values.
    return JSONResponse({"error": "Invalid request"}, status_code=422)
