from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.ai.advisor import ChatMessage, run_turn
from app.ai.explain import stream_explanation
from app.config import Settings, get_settings
from app.domain.catalog import BUCKET_META, GROUP_BUCKETS, LABELS, PRODUCTS
from app.domain.plan import allocate_pct, analyse, limits, project, valid_pct
from app.domain.schemas import PctModel, Profile, Risk
from app.domain.sources import SOURCES

router = APIRouter(prefix="/api")


def ai_error(e: BaseException) -> HTTPException:
    """Map an AI-provider failure to a clean client error. Never leaks provider details."""
    print(f"AI error: {type(e).__name__}: {str(e)[:300]}")
    stack = [e]
    while stack:  # FallbackModel raises an exception group when every model failed
        cur = stack.pop()
        if getattr(cur, "status_code", None) == 429:
            return HTTPException(429, "The AI provider's free quota is used up for now. Wait a bit and try again.")
        stack.extend(getattr(cur, "exceptions", []))
    return HTTPException(502, "The AI service is unavailable. Try again in a moment.")
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/catalog")
def catalog():
    """Static reference data the client renders from: labels, buckets, products, sources."""
    return {
        "labels": LABELS,
        "buckets": BUCKET_META,
        "group_buckets": GROUP_BUCKETS,
        "products": {g: [p.model_dump() for p in items] for g, items in PRODUCTS.items()},
        "sources": {k: s.model_dump() for k, s in SOURCES.items()},
    }


class PlanRequest(BaseModel):
    profile: Profile


@router.post("/plan")
def plan(req: PlanRequest):
    return {
        "base": allocate_pct(req.profile),
        "limits": limits(req.profile),
        "analysis": analyse(req.profile),
    }


class ValidateRequest(BaseModel):
    profile: Profile
    pct: PctModel


@router.post("/allocation/validate")
def validate_allocation(req: ValidateRequest):
    return {"valid": valid_pct(req.profile, req.pct.model_dump())}


class ProjectionRequest(BaseModel):
    amount: float = Field(ge=0, le=100_000_000)
    monthly: float = Field(ge=0, le=1_000_000)
    years: int = Field(ge=1, le=50)
    risk: Risk


@router.post("/projection")
def projection(req: ProjectionRequest):
    return {"series": project(req.amount, req.monthly, req.years, req.risk)}


class ExplainRequest(BaseModel):
    profile: Profile
    pct: PctModel | None = None


@router.post("/explain")
async def explain(req: ExplainRequest, settings: SettingsDep):
    base = allocate_pct(req.profile)
    # Use the client's adjusted allocation only if it passes the same guardrails as the default.
    pct = req.pct.model_dump() if req.pct and valid_pct(req.profile, req.pct.model_dump()) else base
    chunks = stream_explanation(settings, req.profile, pct, adjusted=pct != base)
    # Fetch the first chunk before responding so a provider failure becomes a real HTTP error
    # rather than a dropped connection after the headers are sent.
    try:
        first = await anext(chunks)
    except StopAsyncIteration:
        first = ""
    except Exception as e:
        raise ai_error(e) from e

    async def body():
        yield first
        try:
            async for chunk in chunks:
                yield chunk
        except Exception as e:  # mid-stream failure: end the text, keep what was sent
            print(f"explain stream error: {type(e).__name__}: {str(e)[:200]}")

    return StreamingResponse(body(), media_type="text/plain; charset=utf-8")


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=30)
    profile: Profile
    confirmed: list[str]
    pct: PctModel | None = None  # falls back to the rules-based default when the client has none yet
    picks: list[str] = Field(max_length=20)


@router.post("/chat")
async def chat(req: ChatRequest, settings: SettingsDep):
    if req.messages[-1].role != "user":
        raise HTTPException(422, "Last message must be from the user")
    try:
        result = await run_turn(settings, req.messages, req.profile, req.confirmed, req.pct.model_dump() if req.pct else None, req.picks)
    except Exception as e:
        raise ai_error(e) from e
    if result is None:
        raise HTTPException(503, "The advisor needs an AI key. Use the form instead.")
    return result
