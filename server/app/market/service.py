"""Live product data from Yahoo Finance (via the unofficial `yfinance` library: free, no key, may be
delayed or break). Everything degrades gracefully: callers always get the last good snapshot, or an
empty one, and the UI falls back to the static catalog.

Returns, volatility and drawdown are computed here from dividend-adjusted daily prices so units are
consistent (Yahoo's own summary fields mix percents and fractions).
"""

import asyncio
import math
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.domain.catalog import PRODUCTS

SOURCE = "Yahoo Finance via yfinance (unofficial, may be delayed)"
HISTORY_PERIOD = "5y"
RETRY_AFTER_FAILURE_S = 60


def _r(x: float | None, nd: int = 2) -> float | None:
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), nd)


def compute_metrics(closes: pd.Series) -> dict[str, float | None]:
    """Trailing returns (1y total, 3y/5y annualized), volatility and max drawdown, all in percent."""
    closes = closes.dropna()
    if len(closes) < 30:
        return {}
    end, last = closes.index[-1], float(closes.iloc[-1])

    def at(years: int) -> float | None:
        target = end - pd.DateOffset(years=years)
        if closes.index[0] > target + pd.Timedelta(days=10):
            return None  # fund is younger than the window
        before = closes.loc[:target]
        return float(before.iloc[-1] if len(before) else closes.iloc[0])

    def total(years: int) -> float | None:
        p = at(years)
        return None if not p else (last / p - 1) * 100

    def annualized(years: int) -> float | None:
        p = at(years)
        return None if not p else ((last / p) ** (1 / years) - 1) * 100

    daily = (closes / closes.shift(1)).apply(math.log).dropna().iloc[-756:]  # up to ~3 years
    vol = float(daily.std(ddof=1)) * math.sqrt(252) * 100 if len(daily) >= 250 else None
    drawdown = float((closes / closes.cummax() - 1).min()) * 100

    return {
        "ret_1y_pct": _r(total(1)),
        "ret_3y_pct": _r(annualized(3)),
        "ret_5y_pct": _r(annualized(5)),
        "volatility_pct": _r(vol),
        "max_drawdown_pct": _r(drawdown),
    }


MONTHS_KEPT = 61  # month-end closes => up to 60 monthly returns (5 years)


def monthly_closes(daily: pd.Series) -> pd.Series:
    """Month-end dividend-adjusted closes (the last one may be the current partial month)."""
    return daily.dropna().resample("ME").last().dropna().iloc[-MONTHS_KEPT:]


def fetch_market() -> tuple[dict[str, dict[str, Any]], dict[str, pd.Series]]:
    """Blocking: fetch every live catalog product. Per-ticker failures are skipped, not raised.

    Returns (metrics by catalog ticker, monthly closes by catalog ticker)."""
    import yfinance as yf

    wanted = {(p.symbol or p.ticker): p.ticker for items in PRODUCTS.values() for p in items if p.live}
    symbols = list(wanted)

    closes: dict[str, pd.Series] = {}
    try:
        df = yf.download(symbols, period=HISTORY_PERIOD, interval="1d", auto_adjust=True, progress=False, threads=True)
        for sym in symbols:
            try:
                closes[sym] = df["Close"][sym]
            except Exception:
                pass
    except Exception as e:
        print(f"market history error: {type(e).__name__}: {str(e)[:200]}")

    def info_for(sym: str) -> tuple[str, dict[str, Any]]:
        try:
            return sym, yf.Ticker(sym).info or {}
        except Exception as e:
            print(f"market info error {sym}: {type(e).__name__}: {str(e)[:120]}")
            return sym, {}

    with ThreadPoolExecutor(max_workers=6) as pool:
        infos = dict(pool.map(info_for, symbols))

    out: dict[str, dict[str, Any]] = {}
    monthly: dict[str, pd.Series] = {}
    for sym, ticker in wanted.items():
        if sym in closes and len(closes[sym].dropna()) >= 30:
            monthly[ticker] = monthly_closes(closes[sym])
        info = infos.get(sym, {})
        item: dict[str, Any] = {}
        if sym in closes:
            item.update(compute_metrics(closes[sym]))
        item.update(
            {
                "price": _r(info.get("regularMarketPrice") or info.get("navPrice")),
                "currency": info.get("currency"),
                # Yahoo reports the expense ratio already in percent (0.03 means 0.03%).
                "expense_ratio_pct": _r(info.get("netExpenseRatio"), 3),
                # Yahoo reports yield as a fraction (0.0106 means 1.06%).
                "yield_pct": _r((info.get("yield") or 0) * 100) if info.get("yield") is not None else None,
                "aum_usd": info.get("totalAssets"),
                "category": info.get("category"),
            }
        )
        item = {k: v for k, v in item.items() if v is not None}
        if item:
            out[ticker] = item
    return out, monthly


class MarketService:
    """Caches the snapshot; refreshes in the background (stale-while-revalidate)."""

    def __init__(self, fetcher: Callable[[], tuple[dict[str, dict[str, Any]], dict[str, pd.Series]]] = fetch_market, ttl: int = 1800, clock: Callable[[], float] = time.time):
        self.fetcher, self.ttl, self.clock = fetcher, ttl, clock
        self.items: dict[str, dict[str, Any]] = {}
        self.monthly: dict[str, pd.Series] = {}
        self.asof: float | None = None
        self._last_attempt = 0.0
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None

    def snapshot(self) -> dict[str, Any]:
        asof = datetime.fromtimestamp(self.asof, timezone.utc).isoformat() if self.asof else None
        # Copy: callers keep a stable view even if a background refresh updates the cache meanwhile.
        return {"source": SOURCE, "asof": asof, "items": dict(self.items)}

    def monthly_for(self, tickers: list[str]) -> dict[str, pd.Series] | None:
        """Cached monthly closes for every ticker, or None if any is missing. No I/O."""
        return {t: self.monthly[t] for t in tickers} if all(t in self.monthly for t in tickers) else None

    def _fresh(self) -> bool:
        return self.asof is not None and self.clock() - self.asof < self.ttl

    async def refresh(self) -> None:
        async with self._lock:
            if self._fresh():
                return
            self._last_attempt = self.clock()
            try:
                new, new_monthly = await asyncio.to_thread(self.fetcher)
            except Exception as e:
                print(f"market refresh failed: {type(e).__name__}: {str(e)[:200]}")
                return
            if new:  # merge so one flaky ticker doesn't wipe the others
                self.items.update(new)
                self.monthly.update(new_monthly)
                self.asof = self.clock()

    def kick(self) -> None:
        """Start a background refresh unless one is running or we tried very recently."""
        if self._task and not self._task.done():
            return
        if self.clock() - self._last_attempt < RETRY_AFTER_FAILURE_S:
            return
        self._task = asyncio.create_task(self.refresh())

    async def get(self, wait_first_load: bool = True) -> dict[str, Any]:
        if self._fresh():
            return self.snapshot()
        if self.asof is None and wait_first_load:
            try:
                await asyncio.wait_for(self.refresh(), timeout=25)
            except TimeoutError:
                pass
        else:
            self.kick()
        return self.snapshot()
