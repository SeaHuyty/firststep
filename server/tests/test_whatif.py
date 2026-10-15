import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.domain.plan import allocate_pct, project
from app.domain.schemas import Profile
from app.domain.whatif import (
    MIN_MONTHS,
    history_stats,
    portfolio_returns,
    proxies_for,
    simulate,
    weights_for,
    what_if,
)
from app.main import app
from app.market.service import MarketService

PROFILE = {"amount": 10000, "goal": "wealth", "horizon": 7, "emergency": "insufficient", "risk": 2, "debt": "none"}
PCT = {"emergency": 20, "stocks": 40, "bonds": 23, "cash": 12, "alt": 5}


def closes(monthly_return: float, months: int = 61, noise: float = 0.0, seed: int = 1) -> pd.Series:
    """Month-end closes growing at `monthly_return` per month, with optional gaussian noise."""
    rng = np.random.default_rng(seed)
    rets = monthly_return + rng.normal(0, noise, months - 1)
    idx = pd.date_range(end="2026-09-30", periods=months, freq="ME")
    return pd.Series(100 * np.concatenate([[1], np.cumprod(1 + rets)]), index=idx)


# ---- fund mapping ----------------------------------------------------------------------------


def test_defaults_when_nothing_is_picked():
    assert proxies_for("stocks", []) == ["VT"]
    assert proxies_for("bonds", []) == ["BND"]
    assert proxies_for("cash", []) == ["SGOV"] and proxies_for("emergency", []) == ["SGOV"]
    assert proxies_for("alt", ["VOO"]) == ["VNQ"]


def test_picks_override_defaults_within_their_group_only():
    assert proxies_for("stocks", ["VOO", "VTI", "BND"]) == ["VOO", "VTI"]
    assert proxies_for("bonds", ["VOO", "AGG"]) == ["AGG"]


def test_unlisted_and_reit_picks_are_not_used_as_proxies():
    assert proxies_for("cash", ["HYSA", "MMF"]) == ["SGOV"]  # accounts have no price history
    assert proxies_for("stocks", ["VNQ"]) == ["VT"]  # VNQ stands in for the alternatives bucket


def test_weights_sum_to_one_and_merge_shared_funds():
    w, comp = weights_for(PCT, ["VOO", "VTI"])
    assert sum(w.values()) == pytest.approx(1)
    assert w["SGOV"] == pytest.approx(0.32)  # emergency 20 + cash 12
    assert w["VOO"] == pytest.approx(0.20) and w["VTI"] == pytest.approx(0.20)
    assert [c["bucket"] for c in comp] == ["emergency", "stocks", "bonds", "cash", "alt"]


def test_zero_buckets_are_left_out():
    w, comp = weights_for({"emergency": 20, "stocks": 80, "bonds": 0, "cash": 0, "alt": 0}, [])
    assert set(w) == {"SGOV", "VT"} and len(comp) == 2


# ---- statistics ------------------------------------------------------------------------------


def test_portfolio_returns_blend_by_weight():
    r = portfolio_returns({"A": closes(0.02), "B": closes(0.0)}, {"A": 0.5, "B": 0.5})
    assert r is not None and len(r) == 60
    assert r.iloc[0] == pytest.approx(0.01)


def test_portfolio_returns_need_enough_overlap():
    assert portfolio_returns({"A": closes(0.01, months=MIN_MONTHS)}, {"A": 1.0}) is None  # 23 returns
    # A fund that only has 30 months limits the whole mix to those 30 months.
    r = portfolio_returns({"A": closes(0.01), "B": closes(0.01, months=31)}, {"A": 0.5, "B": 0.5})
    assert r is not None and len(r) == 30


def test_history_stats_for_a_steady_climb():
    r = portfolio_returns({"A": closes(0.01)}, {"A": 1.0})
    s = history_stats(r)
    assert s["annual_return_pct"] == pytest.approx(12.7, abs=0.1)
    assert s["volatility_pct"] == pytest.approx(0, abs=0.01) and s["max_drawdown_pct"] == 0
    assert s["best_12m_pct"] == pytest.approx(s["worst_12m_pct"], abs=0.01)
    assert s["window"]["months"] == 60 and s["window"]["end"] == "Sep 2026"


def test_history_stats_see_a_crash():
    c = closes(0.01)
    c.iloc[30:] *= 0.6  # prices fall to 60% of trend in one month, which also includes that month's +1%
    s = history_stats(portfolio_returns({"A": c}, {"A": 1.0}))
    assert s["max_drawdown_pct"] == pytest.approx((0.6 * 1.01 - 1) * 100, abs=0.1) and s["worst_12m_pct"] < -20


# ---- simulation ------------------------------------------------------------------------------


def test_simulation_of_a_constant_return_matches_the_closed_form():
    bands, loss = simulate(np.full(60, 0.005), amount=10000, monthly=100, years=5)
    expected = 10000 * 1.005**60 + 100 * (1.005**60 - 1) / 0.005
    assert bands[0][-1] == bands[1][-1] == bands[2][-1] == pytest.approx(expected, abs=1)
    assert bands[1][0] == 10000 and len(bands[1]) == 6 and loss == 0


def test_simulation_is_deterministic_and_ordered():
    r = portfolio_returns({"A": closes(0.006, noise=0.03)}, {"A": 1.0}).to_numpy()
    a, loss_a = simulate(r, 10000, 100, 10)
    b, loss_b = simulate(r, 10000, 100, 10)
    assert a == b and loss_a == loss_b  # fixed seed: sliders don't make the chart jitter
    weak, typical, strong = a
    assert all(w <= t <= s for w, t, s in zip(weak, typical, strong))
    assert weak[-1] < typical[-1] < strong[-1]


def test_a_losing_history_gives_a_high_chance_of_loss():
    _, loss = simulate(np.full(60, -0.01), 10000, 100, 10)
    assert loss == 1.0


# ---- orchestration ---------------------------------------------------------------------------


def run(basis, closes_for, **over):
    args = dict(amount=10000, monthly=100, years=10, risk=2, pct=PCT, picks=[], basis=basis, closes_for=closes_for)
    return what_if(**{**args, **over})


def test_history_basis_uses_live_data_when_available():
    data = {t: closes(0.004, noise=0.02, seed=i) for i, t in enumerate(["SGOV", "VT", "BND", "VNQ"])}
    d = run("history", lambda ts: {t: data[t] for t in ts})
    assert d["basis"] == "history" and d["stats"]["window"]["months"] == 60
    assert d["loss_chance_pct"] is not None and d["contributed"] == 22000


def test_falls_back_to_assumptions_when_history_is_missing_or_short():
    for closes_for in (lambda ts: None, lambda ts: {t: closes(0.004, months=20) for t in ts}):
        d = run("history", closes_for)
        assert d["basis"] == "assumed" and d["fallback_reason"] and d["stats"] is None
        assert d["series"] == project(10000, 100, 10, 2)


def test_assumed_basis_never_looks_at_history():
    d = run("assumed", lambda ts: pytest.fail("history should not be requested"))
    assert d["basis"] == "assumed" and d["fallback_reason"] is None


# ---- endpoint --------------------------------------------------------------------------------


@pytest.fixture
def client():
    original = app.state.market
    service = MarketService(fetcher=lambda: ({}, {}), ttl=10**9)
    service.monthly = {t: closes(0.004, noise=0.02, seed=i) for i, t in enumerate(["SGOV", "VT", "BND", "VNQ", "VOO", "VTI"])}
    service.asof = service.clock()
    app.state.market = service
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, market_enabled=True)
    yield TestClient(app)
    app.dependency_overrides.clear()
    app.state.market = original


BODY = {"profile": PROFILE, "pct": PCT, "picks": [], "monthly": 100, "years": 10, "risk": 2, "basis": "history"}


def test_endpoint_uses_history_and_the_current_plan(client):
    d = client.post("/api/whatif", json=BODY).json()
    assert d["basis"] == "history" and d["allocation"] == PCT
    assert [c["bucket"] for c in d["composition"]] == ["emergency", "stocks", "bonds", "cash", "alt"]
    assert len(d["series"]) == 3 and len(d["series"][0]) == 11


def test_endpoint_picks_change_the_mix(client):
    d = client.post("/api/whatif", json={**BODY, "picks": ["VOO", "VTI"]}).json()
    stocks = next(c for c in d["composition"] if c["bucket"] == "stocks")
    assert stocks["tickers"] == ["VOO", "VTI"]


def test_changing_risk_rederives_the_allocation(client):
    d = client.post("/api/whatif", json={**BODY, "risk": 3}).json()
    p3 = Profile(**{**PROFILE, "risk": 3})
    assert d["allocation"] == allocate_pct(p3) != PCT


def test_an_invalid_current_plan_is_ignored(client):
    bad = {"emergency": 0, "stocks": 100, "bonds": 0, "cash": 0, "alt": 0}
    d = client.post("/api/whatif", json={**BODY, "pct": bad}).json()
    assert d["allocation"] == allocate_pct(Profile(**PROFILE))


def test_the_assumed_basis_can_be_requested_explicitly(client):
    d = client.post("/api/whatif", json={**BODY, "basis": "assumed"}).json()
    assert d["basis"] == "assumed" and d["series"] == project(10000, 100, 10, 2)
