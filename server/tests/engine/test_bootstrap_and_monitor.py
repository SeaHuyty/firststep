from dataclasses import dataclass
from decimal import Decimal

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.types import AssetClass, RiskRating, Side
from app.engine.bootstrap import (
    block_paths,
    portfolio_returns,
    project_outcomes,
    rolling_extremes,
)
from app.engine.monitor import (
    drawdown_pct,
    drift,
    needs_cooling_off,
    next_nav,
    rebalance_trades,
    weights_pct,
)

RNG = np.random.default_rng(1)
HISTORY = RNG.normal(0.006, 0.04, 312)


def test_portfolio_returns_blend_classes_and_subtract_the_fee() -> None:
    series = {AssetClass.CASH: [0.01, 0.01], AssetClass.US_EQUITY: [0.03, -0.01]}
    out = portfolio_returns({AssetClass.CASH: 50, AssetClass.US_EQUITY: 50}, series, fee_pct=1.2)
    assert out.tolist() == pytest.approx([0.02 - 0.001, 0.0 - 0.001])


def test_blocks_are_contiguous_runs_of_history() -> None:
    history = np.arange(100, dtype=np.float64)
    paths = block_paths(history, 24, 50, 12, seed=3)
    assert paths.shape == (50, 24)
    for block in paths.reshape(50, 2, 12).reshape(-1, 12):
        assert np.all(np.diff(block) == 1)


def test_history_shorter_than_a_block_is_an_error() -> None:
    with pytest.raises(ValueError, match="shorter"):
        block_paths(np.zeros(5), 12, 1, 12, seed=1)


def test_outcomes_are_ordered_and_start_at_the_lump_sum() -> None:
    r = project_outcomes(HISTORY, lump_sum_usd=6000, monthly_usd=300, years=10, goal_usd=60000)
    assert r.years == tuple(range(11))
    assert r.p10[0] == r.p50[0] == r.p90[0] == 6000
    assert all(lo <= mid <= hi for lo, mid, hi in zip(r.p10, r.p50, r.p90, strict=True))
    assert r.paid_in[-1] == 6000 + 300 * 120
    assert 0 <= r.prob_loss_year1 <= 1
    assert r.prob_reach_goal is not None


def test_outcomes_are_reproducible() -> None:
    a = project_outcomes(HISTORY, lump_sum_usd=1000, monthly_usd=0, years=3)
    b = project_outcomes(HISTORY, lump_sum_usd=1000, monthly_usd=0, years=3)
    assert a == b
    assert a.prob_reach_goal is None


def test_zero_returns_give_exactly_the_money_paid_in() -> None:
    r = project_outcomes(np.zeros(60), lump_sum_usd=1000, monthly_usd=100, years=2, n_paths=10)
    assert r.p10 == r.p50 == r.p90 == (1000, 2200, 3400)
    assert r.prob_loss_year1 == 0


def test_years_must_be_positive() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        project_outcomes(HISTORY, lump_sum_usd=1, monthly_usd=0, years=0)


@settings(max_examples=25, deadline=None)
@given(st.integers(1, 15), st.floats(0, 50000), st.floats(0, 2000))
def test_percentiles_never_cross(years: int, lump: float, monthly: float) -> None:
    r = project_outcomes(HISTORY, lump_sum_usd=lump, monthly_usd=monthly, years=years, n_paths=300)
    assert all(lo <= mid <= hi for lo, mid, hi in zip(r.p10, r.p50, r.p90, strict=True))


def test_nav_subtracts_a_twelfth_of_the_fee() -> None:
    assert next_nav(10.0, 0.01, 1.2) == pytest.approx(10.0 * 1.009)


@dataclass(frozen=True)
class F:
    id: str
    asset_class: AssetClass
    risk_rating: RiskRating = RiskRating.R1
    ter_pct: float = 0.0


FUNDS = {"B": F("B", AssetClass.BONDS), "S": F("S", AssetClass.US_EQUITY)}
TARGET = {"B": 50.0, "S": 50.0}
D = Decimal


def test_weights_pct_of_an_empty_account_are_zero() -> None:
    assert weights_pct({"B": D(0)}) == {"B": 0.0}


def test_drift_01_allows_five_points() -> None:
    result = drift({"B": D(45), "S": D(55)}, TARGET, FUNDS, max_drift_pts=5)
    assert result.max_drift_pts == pytest.approx(5)
    assert not result.needs_rebalance


def test_drift_01_flags_more_than_five_points() -> None:
    result = drift({"B": D(40), "S": D(60)}, TARGET, FUNDS, max_drift_pts=5)
    assert result.by_class[AssetClass.US_EQUITY] == pytest.approx(10)
    assert result.needs_rebalance


def test_rebalance_sells_the_overweight_and_buys_the_underweight() -> None:
    trades = rebalance_trades({"B": D(400), "S": D(600)}, TARGET)
    assert [(t.product_id, t.side, t.amount_usd) for t in trades] == [
        ("S", Side.SELL, D("100.00")),
        ("B", Side.BUY, D("100.00")),
    ]


@given(st.integers(1, 10_000), st.integers(1, 10_000))
def test_rebalance_trades_net_to_zero(bonds: int, stocks: int) -> None:
    trades = rebalance_trades({"B": D(bonds), "S": D(stocks)}, TARGET)
    net = sum((t.amount_usd if t.side == Side.BUY else -t.amount_usd) for t in trades)
    assert abs(net) <= D("0.01")


@pytest.mark.parametrize(
    ("history", "expected"),
    [([], 0), ([100, 120, 90], 25), ([100, 110], 0), ([0, 0], 0)],
)
def test_drawdown_from_peak(history: list[float], expected: float) -> None:
    assert drawdown_pct(history) == pytest.approx(expected)


def cool(sell: int, drawdown: float) -> bool:
    return needs_cooling_off(
        sell_usd=D(sell),
        portfolio_usd=D(1000),
        drawdown=drawdown,
        drawdown_pct_limit=15,
        sell_share_pct_limit=20,
    )


def test_cool_01_blocks_a_big_sale_in_a_big_drop() -> None:
    assert cool(500, 25)


def test_cool_01_allows_a_small_sale_in_a_big_drop() -> None:
    assert not cool(200, 25)


def test_cool_01_allows_a_big_sale_in_a_small_drop() -> None:
    assert not cool(500, 15)


def test_cool_01_ignores_an_empty_portfolio() -> None:
    assert not needs_cooling_off(
        sell_usd=D(1),
        portfolio_usd=D(0),
        drawdown=50,
        drawdown_pct_limit=15,
        sell_share_pct_limit=20,
    )


def test_rolling_extremes_find_the_worst_and_best_year() -> None:
    monthly = np.array([0.0] * 12 + [-0.1] + [0.0] * 11 + [0.05] * 12)
    worst, best = rolling_extremes(monthly)
    assert worst == pytest.approx(-0.1)
    assert best == pytest.approx(1.05**12 - 1)


def test_rolling_extremes_need_a_full_window() -> None:
    with pytest.raises(ValueError, match="shorter"):
        rolling_extremes(np.zeros(5))
