"""Fund prices over time, drift (DRIFT-01) and drawdowns (COOL-01)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.core.types import AssetClass, Money, Side, to_money
from app.engine.allocation import split_amount
from app.engine.suitability import Fund, weights_by_class

DRIFT_01 = "DRIFT-01"
COOL_01 = "COOL-01"


def next_nav(nav: float, asset_return: float, ter_pct: float) -> float:
    """Return a fund's next monthly price: asset return minus fee/12."""
    return nav * (1 + asset_return - ter_pct / 100 / 12)


def weights_pct(values: Mapping[str, Money]) -> dict[str, float]:
    """Return each holding's share of the total, in percent."""
    total = sum(values.values(), Decimal(0))
    if total <= 0:
        return dict.fromkeys(values, 0.0)
    return {pid: float(v / total * 100) for pid, v in values.items()}


@dataclass(frozen=True, slots=True)
class Drift:
    """How far each asset class is from target, in percentage points."""

    by_class: dict[AssetClass, float]
    max_drift_pts: float
    needs_rebalance: bool


def drift(
    values: Mapping[str, Money],
    target_weights: Mapping[str, float],
    funds: Mapping[str, Fund],
    max_drift_pts: float,
) -> Drift:
    """Return drift per asset class against the target portfolio."""
    current = weights_by_class(weights_pct(values), funds)
    target = weights_by_class(target_weights, funds)
    by_class = {a: current.get(a, 0.0) - target.get(a, 0.0) for a in set(current) | set(target)}
    worst = max((abs(d) for d in by_class.values()), default=0.0)
    return Drift(by_class=by_class, max_drift_pts=worst, needs_rebalance=worst > max_drift_pts)


@dataclass(frozen=True, slots=True)
class Trade:
    """One order needed to move holdings to target."""

    product_id: str
    side: Side
    amount_usd: Money


def rebalance_trades(
    values: Mapping[str, Money], target_weights: Mapping[str, float]
) -> tuple[Trade, ...]:
    """Return the sells and buys that restore the target weights.

    Sells and buys net to zero; trades under one dollar are skipped.
    """
    total = sum(values.values(), Decimal(0))
    targets = {line.product_id: line.amount_usd for line in split_amount(target_weights, total)}
    trades = []
    for pid in sorted(set(values) | set(targets)):
        gap = targets.get(pid, Decimal(0)) - values.get(pid, Decimal(0))
        if abs(gap) >= 1:
            trades.append(Trade(pid, Side.BUY if gap > 0 else Side.SELL, to_money(abs(gap))))
    return tuple(sorted(trades, key=lambda t: (t.side != Side.SELL, t.product_id)))


def drawdown_pct(history: Sequence[float]) -> float:
    """Return how far the latest value is below its peak, in percent."""
    if not history:
        return 0.0
    peak = max(history)
    return 0.0 if peak <= 0 else max(0.0, (peak - history[-1]) / peak * 100)


def needs_cooling_off(
    *,
    sell_usd: Money,
    portfolio_usd: Money,
    drawdown: float,
    drawdown_pct_limit: float,
    sell_share_pct_limit: float,
) -> bool:
    """Return whether a sale must wait (COOL-01).

    It must wait when the portfolio is down more than the drawdown
    limit and the sale is more than the share limit of the portfolio.
    """
    if portfolio_usd <= 0:
        return False
    share = float(sell_usd / portfolio_usd * 100)
    return drawdown > drawdown_pct_limit and share > sell_share_pct_limit
