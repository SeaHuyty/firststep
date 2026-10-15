from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.ai.advisor import ChatMessage, run_turn
from app.ai.explain import stream_explanation
from app.config import Settings, get_settings
from app.domain.catalog import BUCKET_META, GROUP_BUCKETS, LABELS, PRODUCTS
from app.domain.plan import allocate_pct, analyse, limits, suggest_picks, valid_pct
from app.domain.schemas import PctModel, Profile, Risk
from app.domain.sources import SOURCES
from app.domain.stocks import SATELLITE, select_stocks, universe
from app.domain.whatif import what_if

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
        "stock_universe": universe(),
        "satellite": SATELLITE,
    }


@router.get("/market")
async def market(request: Request, settings: SettingsDep):
    """Live product metrics keyed by catalog ticker. Empty `items` when the data source is unavailable."""
    service = request.app.state.market
    if not settings.market_enabled:
        return {**service.snapshot(), "items": {}}
    return await service.get()


@router.get("/stocks")
async def stocks(risk: Annotated[int, Query(ge=1, le=3)], request: Request, settings: SettingsDep):
    """Individual stocks screened from the S&P 500 for a risk level, using live price history. The first
    load takes about a minute; until then `ready` is false and the client asks again."""
    service = request.app.state.stocks
    if not settings.market_enabled:
        return {"ready": False, "asof": None, "picks": []}
    service.kick()
    snap = service.snapshot()
    picks = select_stocks(snap["items"], risk) if snap["items"] else []
    return {"ready": bool(picks), "asof": snap["asof"], "picks": picks}


class PlanRequest(BaseModel):
    profile: Profile


@router.post("/plan")
def plan(req: PlanRequest):
    base = allocate_pct(req.profile)
    return {
        "base": base,
        "limits": limits(req.profile),
        "analysis": analyse(req.profile),
        "picks": suggest_picks(req.profile.risk, base["alt"]),
    }


class ValidateRequest(BaseModel):
    profile: Profile
    pct: PctModel


@router.post("/allocation/validate")
def validate_allocation(req: ValidateRequest):
    return {"valid": valid_pct(req.profile, req.pct.model_dump())}


class WhatIfRequest(BaseModel):
    profile: Profile
    pct: PctModel | None = None  # the plan currently shown, if any
    picks: list[str] = Field(default_factory=list, max_length=20)
    monthly: float = Field(ge=0, le=1_000_000)
    years: int = Field(ge=1, le=50)
    risk: Risk
    basis: Literal["history", "assumed"] = "history"


@router.post("/whatif")
async def whatif(req: WhatIfRequest, request: Request, settings: SettingsDep):
    """Project the plan forward. `history` bootstraps the mix's own live price history; `assumed` (and the
    fallback when data is missing) uses fixed per-risk return assumptions."""
    # Changing risk re-derives the allocation; the client's current plan only applies at its own risk level.
    profile = req.profile.model_copy(update={"risk": req.risk})
    given = req.pct.model_dump() if req.pct else None
    pct = given if req.risk == req.profile.risk and given and valid_pct(profile, given) else allocate_pct(profile)

    service = request.app.state.market
    if req.basis == "history" and settings.market_enabled:
        await service.get()  # first call waits for the initial load; afterwards this is a cache read
    return what_if(
        amount=req.profile.amount,
        monthly=req.monthly,
        years=req.years,
        risk=req.risk,
        pct=pct,
        picks=req.picks,
        basis=req.basis if settings.market_enabled else "assumed",
        closes_for=lambda tickers: monthly_for(request, tickers),
    )


def monthly_for(request: Request, tickers: list[str]):
    """Monthly closes for funds (market service) and S&P 500 stocks (screen service); None if any is missing."""
    have = {**request.app.state.stocks.monthly, **request.app.state.market.monthly}
    return {t: have[t] for t in tickers} if all(t in have for t in tickers) else None


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
async def chat(req: ChatRequest, request: Request, settings: SettingsDep):
    if req.messages[-1].role != "user":
        raise HTTPException(422, "Last message must be from the user")
    service = request.app.state.market
    live = service.snapshot()["items"] if settings.market_enabled else {}
    if settings.market_enabled:
        service.kick()  # never block a chat turn on market data; refresh in the background if stale
    shortlist: list[dict] = []
    if settings.market_enabled:
        snap = request.app.state.stocks.snapshot()
        shortlist = select_stocks(snap["items"], req.profile.risk) if snap["items"] else []
    try:
        result = await run_turn(
            settings, req.messages, req.profile, req.confirmed, req.pct.model_dump() if req.pct else None, req.picks, live, shortlist
        )
    except Exception as e:
        raise ai_error(e) from e
    if result is None:
        raise HTTPException(503, "The advisor needs an AI key. Use the form instead.")
    return result
