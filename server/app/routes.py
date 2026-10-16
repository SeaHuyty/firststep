"""HTTP routes. Thin: parse the request, call the domain or AI layer."""

import logging
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal

import pandas as pd
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
from app.domain.stocks import select_stocks, universe
from app.domain.whatif import holdings, what_if

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def ai_error(e: BaseException) -> HTTPException:
    """Map an AI-provider failure to a clean client error.

    Never leaks provider details.
    """
    logger.warning("AI error: %s: %s", type(e).__name__, str(e)[:300])
    stack = [e]
    while stack:  # FallbackModel raises an exception group when every model failed
        cur = stack.pop()
        if getattr(cur, "status_code", None) == 429:
            return HTTPException(
                429,
                "The AI provider's free quota is used up for now. Wait a bit and try again.",
            )
        stack.extend(getattr(cur, "exceptions", []))
    return HTTPException(502, "The AI service is unavailable. Try again in a moment.")


SettingsDep = Annotated[Settings, Depends(get_settings)]


# Routes return plain dicts. `response_model=None` keeps FastAPI from
# deriving a response model from the return annotation, so responses are
# serialised exactly as before the annotations were added.


@router.get("/health", response_model=None)
def health() -> dict[str, bool]:
    """Return a liveness flag."""
    return {"ok": True}


@router.get("/catalog", response_model=None)
def catalog() -> dict[str, Any]:
    """Return the static reference data the client renders from.

    That is labels, buckets, products, sources and the stock universe.
    """
    return {
        "labels": LABELS,
        "buckets": BUCKET_META,
        "group_buckets": GROUP_BUCKETS,
        "products": {g: [p.model_dump() for p in items] for g, items in PRODUCTS.items()},
        "sources": {k: s.model_dump() for k, s in SOURCES.items()},
        "stock_universe": universe(),
    }


@router.get("/market", response_model=None)
async def market(request: Request, settings: SettingsDep) -> dict[str, Any]:
    """Return live product metrics keyed by catalog ticker.

    `items` is empty when the data source is unavailable.
    """
    service = request.app.state.market
    if not settings.market_enabled:
        return {**service.snapshot(), "items": {}}
    snapshot: dict[str, Any] = await service.get()
    return snapshot


@router.get("/stocks", response_model=None)
async def stocks(
    risk: Annotated[int, Query(ge=1, le=3)], request: Request, settings: SettingsDep
) -> dict[str, Any]:
    """Return S&P 500 stocks screened for a risk level on live prices.

    The first load takes about a minute; until then `ready` is false and
    the client asks again.
    """
    service = request.app.state.stocks
    if not settings.market_enabled:
        return {"ready": False, "asof": None, "picks": []}
    service.kick()
    snap = service.snapshot()
    picks = select_stocks(snap["items"], risk) if snap["items"] else []
    return {"ready": bool(picks), "asof": snap["asof"], "picks": picks}


class PlanRequest(BaseModel):
    """Body of POST /plan."""

    profile: Profile


@router.post("/plan", response_model=None)
def plan(req: PlanRequest) -> dict[str, Any]:
    """Return the default allocation, its limits, analysis and picks."""
    base = allocate_pct(req.profile)
    return {
        "base": base,
        "limits": limits(req.profile),
        "analysis": analyse(req.profile),
        "picks": suggest_picks(req.profile.risk, base["alt"]),
    }


class ValidateRequest(BaseModel):
    """Body of POST /allocation/validate."""

    profile: Profile
    pct: PctModel


@router.post("/allocation/validate", response_model=None)
def validate_allocation(req: ValidateRequest) -> dict[str, bool]:
    """Return whether an allocation passes the profile's guardrails."""
    return {"valid": valid_pct(req.profile, req.pct.model_dump())}


class WhatIfRequest(BaseModel):
    """Body of POST /whatif."""

    profile: Profile
    pct: PctModel | None = None  # the plan currently shown, if any
    picks: list[str] = Field(default_factory=list, max_length=20)
    monthly: float = Field(ge=0, le=1_000_000)
    years: int = Field(ge=1, le=50)
    risk: Risk
    basis: Literal["history", "assumed"] = "history"


@router.post("/whatif", response_model=None)
async def whatif(req: WhatIfRequest, request: Request, settings: SettingsDep) -> dict[str, Any]:
    """Project the plan forward.

    `history` bootstraps the mix's own live price history; `assumed`
    (and the fallback when data is missing) uses fixed per-risk return
    assumptions.
    """
    # Changing risk re-derives the allocation; the client's current plan
    # only applies at its own risk level.
    profile = req.profile.model_copy(update={"risk": req.risk})
    given = req.pct.model_dump() if req.pct else None
    pct = (
        given
        if req.risk == req.profile.risk and given and valid_pct(profile, given)
        else allocate_pct(profile)
    )

    service = request.app.state.market
    if req.basis == "history" and settings.market_enabled:
        # The first call waits for the initial load; afterwards this is
        # a cache read.
        await service.get()
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


class HoldingsRequest(BaseModel):
    """Body of POST /holdings."""

    profile: Profile
    pct: PctModel | None = None
    picks: list[str] = Field(default_factory=list, max_length=20)


@router.post("/holdings", response_model=None)
def holdings_route(req: HoldingsRequest) -> dict[str, list[dict[str, Any]]]:
    """Return dollars per fund for the plan shown.

    The what-if tests exactly this split.
    """
    given = req.pct.model_dump() if req.pct else None
    pct = given if given and valid_pct(req.profile, given) else allocate_pct(req.profile)
    return {"holdings": holdings(req.profile.amount, pct, req.picks)}


def monthly_for(request: Request, tickers: list[str]) -> dict[str, pd.Series] | None:
    """Return monthly closes for funds and S&P 500 stocks.

    Funds come from the market service and stocks from the screen
    service. Returns None if any ticker is missing.
    """
    have = {**request.app.state.stocks.monthly, **request.app.state.market.monthly}
    return {t: have[t] for t in tickers} if all(t in have for t in tickers) else None


class ExplainRequest(BaseModel):
    """Body of POST /explain."""

    profile: Profile
    pct: PctModel | None = None


@router.post("/explain")
async def explain(req: ExplainRequest, settings: SettingsDep) -> StreamingResponse:
    """Stream a plain-text, cited explanation of the allocation."""
    base = allocate_pct(req.profile)
    # Use the client's adjusted allocation only if it passes the same
    # guardrails as the default.
    pct = (
        req.pct.model_dump() if req.pct and valid_pct(req.profile, req.pct.model_dump()) else base
    )
    chunks = stream_explanation(settings, req.profile, pct, adjusted=pct != base)
    # Fetch the first chunk before responding so a provider failure
    # becomes a real HTTP error rather than a dropped connection after
    # the headers are sent.
    try:
        first = await anext(chunks)
    except StopAsyncIteration:
        first = ""
    except Exception as e:  # any provider failure becomes a clean HTTP error
        raise ai_error(e) from e

    async def body() -> AsyncIterator[str]:
        yield first
        try:
            async for chunk in chunks:
                yield chunk
        except Exception as e:  # mid-stream failure: end the text, keep what was sent
            logger.warning("explain stream error: %s: %s", type(e).__name__, str(e)[:200])

    return StreamingResponse(body(), media_type="text/plain; charset=utf-8")


class ChatRequest(BaseModel):
    """Body of POST /chat."""

    messages: list[ChatMessage] = Field(min_length=1, max_length=30)
    profile: Profile
    confirmed: list[str]
    # Falls back to the rules-based default when the client has none.
    pct: PctModel | None = None
    picks: list[str] = Field(max_length=20)


@router.post("/chat", response_model=None)
async def chat(req: ChatRequest, request: Request, settings: SettingsDep) -> dict[str, Any]:
    """Run one advisor turn; return its reply and proposed actions."""
    if req.messages[-1].role != "user":
        raise HTTPException(422, "Last message must be from the user")
    service = request.app.state.market
    live = service.snapshot()["items"] if settings.market_enabled else {}
    if settings.market_enabled:
        # Never block a chat turn on market data; refresh in the
        # background if stale.
        service.kick()
    shortlist: list[dict[str, Any]] = []
    if settings.market_enabled:
        snap = request.app.state.stocks.snapshot()
        shortlist = select_stocks(snap["items"], req.profile.risk) if snap["items"] else []
    try:
        result = await run_turn(
            settings,
            req.messages,
            profile=req.profile,
            confirmed=req.confirmed,
            pct=req.pct.model_dump() if req.pct else None,
            picks=req.picks,
            market=live,
            shortlist=shortlist,
        )
    except Exception as e:  # any provider failure becomes a clean HTTP error
        raise ai_error(e) from e
    if result is None:
        raise HTTPException(503, "The advisor needs an AI key. Use the form instead.")
    return result
