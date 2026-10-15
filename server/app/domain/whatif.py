"""What-if analysis: project a portfolio forward using its own past.

The allocation is mapped to concrete funds (the client's picks, else a default proxy per bucket). The
mix's actual monthly returns over the available window (up to 5 years of live data) are then
bootstrapped (resampled with replacement) into thousands of possible futures. The 10th/50th/90th
percentile paths are the weak/typical/strong scenarios.

Honest limits: the window is short and recent, resampling ignores trends and volatility clustering, and
the past may be kinder or harsher than the future. Callers fall back to the fixed-rate assumptions in
plan.project() whenever there isn't enough live history.
"""

import math
from typing import Any

import numpy as np
import pandas as pd

from .catalog import PRODUCTS, group_of
from .stocks import in_universe
from .plan import project
from .schemas import BUCKETS, Pct

MIN_MONTHS = 24
PATHS = 3000
SEED = 42  # fixed so dragging a slider doesn't make the chart jitter

# Used when the client hasn't picked funds for a bucket.
DEFAULT_PROXY = {"stocks": "VT", "single": "VT", "bonds": "BND", "cash": "SGOV", "emergency": "SGOV", "alt": "VNQ"}
BUCKET_GROUPS = {
    "stocks": {"Global Stocks (ETF)"},
    "single": {"Individual Stocks"},
    "bonds": {"Bonds"},
    "cash": {"Savings"},
    "emergency": {"Savings"},
}


def _is_live(ticker: str) -> bool:
    return in_universe(ticker) or any(p.ticker == ticker and p.live for items in PRODUCTS.values() for p in items)


def proxies_for(bucket: str, picks: list[str]) -> list[str]:
    """Funds that stand in for a bucket: the client's picks for its group, else the default."""
    if bucket == "alt":
        return ["VNQ"]
    chosen = [t for t in picks if group_of(t) in BUCKET_GROUPS[bucket] and _is_live(t) and t != "VNQ"]
    return chosen or [DEFAULT_PROXY[bucket]]


def weights_for(pct: Pct, picks: list[str]) -> tuple[dict[str, float], list[dict[str, Any]]]:
    """Per-fund weights (sum 1) and a per-bucket composition for display."""
    weights: dict[str, float] = {}
    composition: list[dict[str, Any]] = []
    for bucket in BUCKETS:
        if pct[bucket] <= 0:
            continue
        tickers = proxies_for(bucket, picks)
        share = {t: 1 / len(tickers) for t in tickers}
        composition.append({"bucket": bucket, "pct": pct[bucket], "tickers": tickers, "shares": share})
        for t in tickers:
            weights[t] = weights.get(t, 0.0) + pct[bucket] / 100 * share[t]
    return weights, composition


def holdings(amount: float, pct: Pct, picks: list[str]) -> list[dict[str, Any]]:
    """Dollars per fund: the same split the what-if tests, so Allocation, Products and What-if agree.
    Each bucket's dollars match the Allocation figure (amount x pct, to the dollar) and are shared among its funds."""
    out: list[dict[str, Any]] = []
    for c in weights_for(pct, picks)[1]:
        bucket_usd = round(amount * c["pct"] / 100)
        left = bucket_usd
        for i, t in enumerate(c["tickers"]):
            usd = left if i == len(c["tickers"]) - 1 else round(bucket_usd * c["shares"][t])
            left -= usd
            out.append({"ticker": t, "bucket": c["bucket"], "amount": usd})
    return out


def portfolio_returns(closes: dict[str, pd.Series], weights: dict[str, float]) -> pd.Series | None:
    """Monthly returns of the mix, rebalanced to the target weights each month, over the months all
    funds have in common. None if that overlap is too short to learn from."""
    frame = pd.concat({t: closes[t].pct_change() for t in weights}, axis=1, join="inner").dropna()
    if len(frame) < MIN_MONTHS:
        return None
    return (frame * pd.Series(weights)).sum(axis=1)


def history_stats(r: pd.Series) -> dict[str, Any]:
    n = len(r)
    cum = (1 + r).cumprod()
    rolling = (1 + r).rolling(12).apply(np.prod, raw=True) - 1 if n >= 12 else None
    return {
        "annual_return_pct": round(float(cum.iloc[-1] ** (12 / n) - 1) * 100, 1),
        "volatility_pct": round(float(r.std(ddof=1)) * math.sqrt(12) * 100, 1),
        "max_drawdown_pct": round(float((cum / cum.cummax() - 1).min()) * 100, 1),
        "best_12m_pct": None if rolling is None else round(float(rolling.max()) * 100, 1),
        "worst_12m_pct": None if rolling is None else round(float(rolling.min()) * 100, 1),
        "window": {"start": r.index[0].strftime("%b %Y"), "end": r.index[-1].strftime("%b %Y"), "months": n},
    }


def simulate(r: np.ndarray, amount: float, monthly: float, years: int) -> tuple[list[list[int]], float]:
    """Bootstrap futures from monthly returns `r`. Returns ([p10, p50, p90] value per year, P(loss))."""
    months = years * 12
    rng = np.random.default_rng(SEED)
    draws = rng.choice(r, size=(PATHS, months), replace=True)
    value = np.full(PATHS, float(amount))
    by_year = np.empty((PATHS, years + 1))
    by_year[:, 0] = amount
    for m in range(months):
        value = value * (1 + draws[:, m]) + monthly  # contributions at month end, like plan.project()
        if (m + 1) % 12 == 0:
            by_year[:, (m + 1) // 12] = value
    bands = np.percentile(by_year, [10, 50, 90], axis=0)
    contributed = amount + monthly * months
    return [[int(round(v)) for v in band] for band in bands], float((value < contributed).mean())


def what_if(
    *,
    amount: float,
    monthly: float,
    years: int,
    risk: int,
    pct: Pct,
    picks: list[str],
    basis: str,
    closes_for: Any,
) -> dict[str, Any]:
    """`closes_for(tickers)` returns monthly closes by ticker, or None when unavailable."""
    weights, composition = weights_for(pct, picks)
    contributed = int(round(amount + monthly * years * 12))
    base = {"allocation": pct, "composition": composition, "contributed": contributed, "start": round(amount)}

    fallback_reason: str | None = None
    if basis == "history":
        closes = closes_for(list(weights))
        returns = portfolio_returns(closes, weights) if closes else None
        if returns is None:
            fallback_reason = "Not enough live price history for this mix right now, so standard assumptions are used."
        else:
            series, loss = simulate(returns.to_numpy(), amount, monthly, years)
            return {
                **base,
                "basis": "history",
                "fallback_reason": None,
                "series": series,
                "loss_chance_pct": round(loss * 100, 1),
                "stats": history_stats(returns),
            }

    return {
        **base,
        "basis": "assumed",
        "fallback_reason": fallback_reason,
        "series": project(amount, monthly, years, risk),
        "loss_chance_pct": None,
        "stats": None,
    }
