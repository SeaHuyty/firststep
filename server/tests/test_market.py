import asyncio

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.ai.advisor import ChatState, build_system, live_text
from app.config import Settings, get_settings
from app.domain.plan import allocate_pct
from app.domain.schemas import Profile
from app.main import app
from app.market.service import MarketService, compute_metrics

PROFILE = Profile(
    amount=10000, goal="wealth", horizon=7, emergency="insufficient", risk=2, debt="none"
)


def series(daily_growth: float, days: int, crash_at: int | None = None) -> pd.Series:
    idx = pd.bdate_range(end="2026-06-30", periods=days)
    vals = 100 * (1 + daily_growth) ** np.arange(days)
    if crash_at is not None:
        vals[crash_at:] *= 0.7
    return pd.Series(vals, index=idx)


def test_metrics_for_steady_growth():
    m = compute_metrics(
        series(0.10**0 * (1.10 ** (1 / 252) - 1), 5 * 252 + 40)
    )  # ~10%/yr, no noise
    assert m["ret_1y_pct"] == pytest.approx(10, abs=0.5)
    assert m["ret_3y_pct"] == pytest.approx(10, abs=0.5)
    assert m["ret_5y_pct"] == pytest.approx(10, abs=0.5)
    assert m["volatility_pct"] == pytest.approx(0, abs=0.1)
    assert m["max_drawdown_pct"] == 0


def test_metrics_report_a_drawdown():
    m = compute_metrics(series(0.0003, 5 * 252 + 40, crash_at=700))
    assert m["max_drawdown_pct"] == pytest.approx(-30, abs=0.5)


def test_young_fund_has_no_long_windows():
    m = compute_metrics(series(0.0004, 150))
    assert m["ret_1y_pct"] is None
    assert m["ret_3y_pct"] is None
    assert m["ret_5y_pct"] is None
    assert m["volatility_pct"] is None
    assert m["max_drawdown_pct"] is not None


def test_too_little_data_gives_nothing():
    assert compute_metrics(series(0.001, 10)) == {}


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make_service(responses, ttl=100):
    """Return a service whose fetcher yields the given results in order.

    An Exception result means 'Yahoo is down'.
    """
    calls = []
    clock = Clock()

    def fetcher():
        calls.append(clock.t)
        r = responses[min(len(calls), len(responses)) - 1]
        if isinstance(r, Exception):
            raise r
        return r, {}

    return MarketService(fetcher=fetcher, ttl=ttl, clock=clock), clock, calls


def test_first_get_waits_for_data_then_serves_from_cache():
    async def run():
        svc, _clock, calls = make_service([{"VOO": {"price": 1.0}}])
        first = await svc.get()
        second = await svc.get()
        return first, second, calls

    first, second, calls = asyncio.run(run())
    assert first["items"] == {"VOO": {"price": 1.0}}
    assert first["asof"]
    assert second == first
    assert len(calls) == 1


def test_stale_data_is_served_immediately_and_refreshed_in_background():
    async def run():
        svc, clock, calls = make_service([{"VOO": {"price": 1.0}}, {"VOO": {"price": 2.0}}])
        await svc.get()
        clock.t += 500  # past the ttl and past the retry throttle
        stale = await svc.get()
        await svc._task  # let the background refresh finish
        return stale, await svc.get(), len(calls)

    stale, fresh, n = asyncio.run(run())
    assert stale["items"]["VOO"]["price"] == 1.0  # didn't block on the refresh
    assert fresh["items"]["VOO"]["price"] == 2.0
    assert n == 2


def test_failures_keep_the_last_good_snapshot_and_do_not_hammer_the_source():
    async def run():
        svc, clock, calls = make_service([{"VOO": {"price": 1.0}}, RuntimeError("blocked")])
        await svc.get()
        clock.t += 500
        await svc.get()
        await svc._task
        clock.t += 1  # immediately after a failed attempt: throttled
        await svc.get()
        return svc.snapshot(), len(calls)

    snap, n = asyncio.run(run())
    assert snap["items"] == {"VOO": {"price": 1.0}}
    assert n == 2


def test_source_down_from_the_start_returns_an_empty_snapshot():
    async def run():
        svc, _, _ = make_service([RuntimeError("blocked")])
        return await svc.get()

    snap = asyncio.run(run())
    assert snap["items"] == {}
    assert snap["asof"] is None


def test_partial_results_merge_instead_of_wiping_other_tickers():
    async def run():
        svc, clock, _ = make_service(
            [{"VOO": {"price": 1.0}, "BND": {"price": 5.0}}, {"VOO": {"price": 2.0}}]
        )
        await svc.get()
        clock.t += 500
        await svc.get()
        await svc._task
        return svc.snapshot()["items"]

    items = asyncio.run(run())
    assert items == {"VOO": {"price": 2.0}, "BND": {"price": 5.0}}


@pytest.fixture
def client():
    original = app.state.market
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        google_generative_ai_api_key=None,
        anthropic_api_key=None,
        market_enabled=True,
    )
    app.state.market = MarketService(
        fetcher=lambda: (
            {"VOO": {"price": 707.43, "expense_ratio_pct": 0.03, "ret_1y_pct": 17.55}},
            {},
        ),
        ttl=100,
    )
    yield TestClient(app)
    app.dependency_overrides.clear()
    app.state.market = original


def test_market_endpoint(client):
    d = client.get("/api/market").json()
    assert d["items"]["VOO"]["price"] == 707.43
    assert d["asof"]
    assert "Yahoo" in d["source"]


def test_market_endpoint_is_empty_when_disabled():
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, market_enabled=False)
    try:
        d = TestClient(app).get("/api/market").json()
    finally:
        app.dependency_overrides.clear()
    assert d["items"] == {}


def test_catalog_marks_accounts_as_not_live_and_maps_symbols():
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, market_enabled=False)
    try:
        products = TestClient(app).get("/api/catalog").json()["products"]
    finally:
        app.dependency_overrides.clear()
    flat = {p["ticker"]: p for items in products.values() for p in items}
    assert flat["HYSA"]["live"] is False
    assert flat["MMF"]["live"] is False
    assert flat["IWDA"]["symbol"] == "IWDA.L"
    assert flat["VOO"]["live"] is True


def test_advisor_prompt_includes_live_metrics_and_stays_valid_without_them():
    state = ChatState(profile=PROFILE, pct=allocate_pct(PROFILE), known=set())
    live = {
        "VOO": {
            "price": 707.43,
            "expense_ratio_pct": 0.03,
            "yield_pct": 1.06,
            "ret_1y_pct": 17.55,
            "ret_5y_pct": 13.11,
            "volatility_pct": 14.8,
            "max_drawdown_pct": -24.52,
        }
    }
    with_live = build_system(state, [], live)
    assert (
        "LIVE: price $707.43, expense ratio 0.03%, yield 1.1%, return 1y +17.6%, "
        "5y/yr +13.1%, volatility 14.8%, worst drawdown -24.5%." in with_live
    )
    assert "LIVE:" not in build_system(state, [], None).split("How to behave:")[0]
    assert live_text(None) == ""
    assert live_text({}) == ""
