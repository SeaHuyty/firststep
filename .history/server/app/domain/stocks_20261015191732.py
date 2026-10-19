"""Individual-stock screening over the S&P 500.

The system, not a hand-written list, chooses the stocks: every company in the universe is scored on its
own live price history, filtered for the client's risk level, and picked so that no sector dominates.
Deterministic and explainable: the AI only discusses the shortlist it is given and cannot add to it.

Limits: ranks by past price history only (no fundamentals, no forecasts), and past performance does not
predict future results.
"""

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data" / "sp500.csv"
PICKS = 10  # shortlist size
PER_SECTOR = 2  # so the shortlist always spans at least five sectors


@lru_cache
def universe() -> dict[str, dict[str, str]]:
    """symbol (Yahoo style) -> {name, sector}."""
    with DATA.open(encoding="utf-8", newline="") as f:
        return {r["symbol"]: {"name": r["name"], "sector": r["sector"]} for r in csv.DictReader(f)}


def in_universe(ticker: str) -> bool:
    return ticker in universe()


def risk_rating(vol: float) -> int:
    """1-5 scale like the catalog's: single stocks start at 3."""
    return 3 if vol < 25 else 4 if vol < 40 else 5


def _reason(risk: int, m: dict[str, Any]) -> str:
    vol, ret = m["volatility_pct"], m["ret_3y_pct"]
    if risk == 1:
        return f"Steady for a stock: {vol:.0f}% volatility and {ret:+.0f}%/yr over 3 years."
    if risk == 2:
        return f"Balanced: {ret:+.0f}%/yr over 3 years for {vol:.0f}% volatility."
    return f"Growth-oriented: {ret:+.0f}%/yr over 3 years, with {vol:.0f}% volatility."


def select_stocks(stats: dict[str, dict[str, Any]], risk: int, n: int = PICKS) -> list[dict[str, Any]]:
    """Shortlist `n` S&P 500 stocks for a risk level, at most PER_SECTOR from any one sector.

    1 Conservative: the calmest third, best return per unit of volatility.
    2 Moderate: the middle band of volatility, best return per unit of volatility.
    3 Aggressive: the more volatile half, highest 3-year return.
    """
    uni = universe()
    rows = {
        s: m
        for s, m in stats.items()
        if s in uni and m.get("volatility_pct") and m.get("ret_3y_pct") is not None and m.get("price")
    }
    if len(rows) < n * 2:
        return []
    vols = np.array([m["volatility_pct"] for m in rows.values()])
    q = lambda p: float(np.percentile(vols, p))  # noqa: E731

    if risk == 1:
        pool = {s: m for s, m in rows.items() if m["volatility_pct"] <= q(33) and m["ret_3y_pct"] > 0}
        score = lambda m: m["ret_3y_pct"] / m["volatility_pct"]  # noqa: E731
    elif risk == 2:
        pool = {s: m for s, m in rows.items() if q(33) < m["volatility_pct"] <= q(66) and m["ret_3y_pct"] > 0}
        score = lambda m: m["ret_3y_pct"] / m["volatility_pct"]  # noqa: E731
    else:
        pool = {s: m for s, m in rows.items() if m["volatility_pct"] >= q(50)}
        score = lambda m: m["ret_3y_pct"]  # noqa: E731

    picks: list[dict[str, Any]] = []
    per_sector: dict[str, int] = {}
    for sym in sorted(pool, key=lambda s: score(pool[s]), reverse=True):
        sector = uni[sym]["sector"]
        if per_sector.get(sector, 0) >= PER_SECTOR:
            continue
        per_sector[sector] = per_sector.get(sector, 0) + 1
        m = pool[sym]
        picks.append(
            {
                "ticker": sym,
                "name": uni[sym]["name"],
                "sector": sector,
                "risk": risk_rating(m["volatility_pct"]),
                "reason": _reason(risk, m),
                "metrics": {k: m[k] for k in ("price", "ret_1y_pct", "ret_3y_pct", "ret_5y_pct", "volatility_pct", "max_drawdown_pct") if m.get(k) is not None},
            }
        )
        if len(picks) == n:
            break
    return picks
