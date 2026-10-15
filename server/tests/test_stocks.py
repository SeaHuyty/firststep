import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.domain.catalog import group_of
from app.domain.stocks import PER_SECTOR, in_universe, select_stocks, universe
from app.domain.whatif import weights_for
from app.main import app
from app.market.service import MarketService

PCT = {"emergency": 20, "stocks": 32, "single": 8, "bonds": 23, "cash": 12, "alt": 5}


def fake_stats(seed: int = 0) -> dict[str, dict]:
    """Every S&P 500 symbol with random but plausible metrics."""
    rng = np.random.default_rng(seed)
    return {
        s: {
            "price": 100.0,
            "ret_1y_pct": float(rng.normal(10, 20)),
            "ret_3y_pct": float(rng.normal(12, 15)),
            "ret_5y_pct": float(rng.normal(12, 10)),
            "volatility_pct": float(rng.uniform(12, 70)),
            "max_drawdown_pct": -30.0,
        }
        for s in universe()
    }


def test_universe_is_the_sp500_with_sectors():
    uni = universe()
    assert len(uni) > 400 and len({v["sector"] for v in uni.values()}) == 11
    assert in_universe("NVDA") and in_universe("TSLA") and not in_universe("DOGE")
    assert group_of("NVDA") == "Individual Stocks" and group_of("VOO") == "Global Stocks (ETF)"


@pytest.mark.parametrize("risk", [1, 2, 3])
def test_shortlist_is_diversified_across_sectors(risk):
    picks = select_stocks(fake_stats(), risk)
    sectors = [p["sector"] for p in picks]
    assert len(picks) == 10 and len(set(p["ticker"] for p in picks)) == 10
    assert max(sectors.count(s) for s in set(sectors)) <= PER_SECTOR and len(set(sectors)) >= 5


def test_risk_level_changes_the_kind_of_stock():
    stats = fake_stats()
    vol = {r: np.mean([p["metrics"]["volatility_pct"] for p in select_stocks(stats, r)]) for r in (1, 2, 3)}
    assert vol[1] < vol[2] < vol[3]


def test_conservative_never_picks_a_loser_and_ignores_missing_data():
    stats = fake_stats()
    stats["NVDA"] = {}  # no history yet
    picks = select_stocks(stats, 1)
    assert all(p["metrics"]["ret_3y_pct"] > 0 for p in picks) and "NVDA" not in {p["ticker"] for p in picks}


def test_too_little_data_gives_no_shortlist():
    assert select_stocks({"NVDA": fake_stats()["NVDA"]}, 2) == []


def test_individual_stocks_have_their_own_slice():
    w, comp = weights_for(PCT, ["NVDA", "TSLA"])
    single = next(c for c in comp if c["bucket"] == "single")
    assert single["tickers"] == ["NVDA", "TSLA"]
    assert w["NVDA"] == w["TSLA"] == pytest.approx(0.08 / 2)
    assert w["VT"] == pytest.approx(0.32)  # the stocks slice stays in the default fund
    assert sum(w.values()) == pytest.approx(1)


def test_no_stock_picks_keeps_the_slice_in_a_fund():
    w, comp = weights_for(PCT, ["VOO"])
    assert next(c for c in comp if c["bucket"] == "single")["tickers"] == ["VT"]
    assert w["VOO"] == pytest.approx(0.32) and w["VT"] == pytest.approx(0.08)


def test_ninety_percent_in_individual_stocks_is_possible_when_aggressive():
    from app.domain.plan import apply_targets, limits, valid_pct
    from app.domain.schemas import Profile

    p = Profile(amount=10000, goal="wealth", horizon=12, emergency="enough", risk=3, debt="none")
    pct, _ = apply_targets(p, {"emergency": 5, "stocks": 55, "single": 14, "bonds": 14, "cash": 7, "alt": 5}, {"single": 90})
    assert pct["single"] == 90 and sum(pct.values()) == 100 and valid_pct(p, pct)
    assert pct["emergency"] >= limits(p)["min"]["emergency"]
    # a moderate client cannot go that far
    q = p.model_copy(update={"risk": 2})
    capped, notes = apply_targets(q, pct, {"single": 90})
    assert capped["single"] <= limits(q)["equity"]["max"] and notes


@pytest.fixture
def client():
    original = app.state.stocks
    service = MarketService(fetcher=lambda: ({}, {}), ttl=10**9)
    service.items = fake_stats()
    service.asof = service.clock()
    app.state.stocks = service
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, market_enabled=True)
    yield TestClient(app)
    app.dependency_overrides.clear()
    app.state.stocks = original


def test_endpoint_returns_a_shortlist_for_the_risk_level(client):
    d = client.get("/api/stocks", params={"risk": 3}).json()
    assert d["ready"] and len(d["picks"]) == 10 and {"ticker", "name", "sector", "reason", "metrics", "risk"} <= set(d["picks"][0])


def test_endpoint_is_not_ready_while_the_screen_loads(client):
    app.state.stocks.items = {}
    d = client.get("/api/stocks", params={"risk": 2}).json()
    assert d["ready"] is False and d["picks"] == []


def test_endpoint_rejects_a_bad_risk(client):
    assert client.get("/api/stocks", params={"risk": 9}).status_code == 422
