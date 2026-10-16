"""Live product data from Yahoo Finance.

Data comes via the unofficial `yfinance` library: free, no key, may be
delayed or break. Everything degrades gracefully: callers always get the
last good snapshot, or an empty one, and the UI falls back to the static
catalog.

Returns, volatility and drawdown are computed here from
dividend-adjusted daily prices so units are consistent (Yahoo's own
summary fields mix percents and fractions).
"""

import asyncio
import contextlib
import logging
import math
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import yfinance as yf

from app.domain.catalog import PRODUCTS
from app.domain.stocks import universe

SOURCE = "Yahoo Finance via yfinance (unofficial, may be delayed)"
HISTORY_PERIOD = "5y"
RETRY_AFTER_FAILURE_S = 60

logger = logging.getLogger(__name__)

# Fetcher result: (metrics by ticker, monthly closes by ticker).
Snapshot = tuple[dict[str, dict[str, Any]], dict[str, pd.Series]]


def _r(x: float | None, nd: int = 2) -> float | None:
    """Round to `nd` places; None for missing or non-finite values."""
    return (
        None
        if x is None or (isinstance(x, float) and not math.isfinite(x))
        else round(float(x), nd)
    )


def compute_metrics(closes: pd.Series) -> dict[str, float | None]:
    """Return trailing returns, volatility and max drawdown, in percent.

    Returns are 1y total and 3y/5y annualized.
    """
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
    """Return month-end dividend-adjusted closes.

    The last one may be the current, partial month.
    """
    return daily.dropna().resample("ME").last().dropna().iloc[-MONTHS_KEPT:]


def fetch_market() -> Snapshot:
    """Fetch every live catalog product. Blocking.

    Per-ticker failures are skipped, not raised.

    Returns:
        (metrics by catalog ticker, monthly closes by catalog ticker).
    """
    wanted = {
        (p.symbol or p.ticker): p.ticker for items in PRODUCTS.values() for p in items if p.live
    }
    symbols = list(wanted)

    closes: dict[str, pd.Series] = {}
    try:
        df = yf.download(
            symbols,
            period=HISTORY_PERIOD,
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        for sym in symbols:
            # A ticker missing from the download is skipped.
            with contextlib.suppress(Exception):
                closes[sym] = df["Close"][sym]
    except Exception as e:  # the data source is unofficial; degrade, never raise
        logger.warning("market history error: %s: %s", type(e).__name__, str(e)[:200])

    def info_for(sym: str) -> tuple[str, dict[str, Any]]:
        try:
            return sym, yf.Ticker(sym).info or {}
        except Exception as e:  # one bad ticker must not fail the others
            logger.warning("market info error %s: %s: %s", sym, type(e).__name__, str(e)[:120])
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
                # Yahoo reports the expense ratio already in percent
                # (0.03 means 0.03%).
                "expense_ratio_pct": _r(info.get("netExpenseRatio"), 3),
                # Yahoo reports yield as a fraction (0.0106 is 1.06%).
                "yield_pct": _r((info.get("yield") or 0) * 100)
                if info.get("yield") is not None
                else None,
                "aum_usd": info.get("totalAssets"),
                "category": info.get("category"),
            }
        )
        item = {k: v for k, v in item.items() if v is not None}
        if item:
            out[ticker] = item
    return out, monthly


def fetch_stocks() -> Snapshot:
    """Fetch price history for the whole S&P 500 universe. Blocking.

    One batched download, history only.
    """
    symbols = list(universe())
    try:
        df = yf.download(
            symbols,
            period=HISTORY_PERIOD,
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as e:  # the data source is unofficial; degrade, never raise
        logger.warning("stock universe error: %s: %s", type(e).__name__, str(e)[:200])
        return {}, {}
    out: dict[str, dict[str, Any]] = {}
    monthly: dict[str, pd.Series] = {}
    for sym in symbols:
        try:
            closes = df["Close"][sym].dropna()
        except Exception:  # a ticker missing from the download is skipped
            logger.debug("no price history for %s", sym)
            continue
        if len(closes) < 250:
            continue
        monthly[sym] = monthly_closes(closes)
        item = {**compute_metrics(closes), "price": _r(float(closes.iloc[-1]))}
        out[sym] = {k: v for k, v in item.items() if v is not None}
    return out, monthly


class MarketService:
    """Cache the snapshot and refresh it in the background.

    Callers get stale data while a refresh runs
    (stale-while-revalidate).
    """

    def __init__(
        self,
        fetcher: Callable[[], Snapshot] = fetch_market,
        ttl: int = 1800,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Create an empty cache; nothing is fetched until asked."""
        self.fetcher, self.ttl, self.clock = fetcher, ttl, clock
        self.items: dict[str, dict[str, Any]] = {}
        self.monthly: dict[str, pd.Series] = {}
        self.asof: float | None = None
        self._last_attempt = 0.0
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None

    def snapshot(self) -> dict[str, Any]:
        """Return the cached items with their source and as-of time."""
        asof = datetime.fromtimestamp(self.asof, UTC).isoformat() if self.asof else None
        # Copy: callers keep a stable view even if a background refresh
        # updates the cache meanwhile.
        return {"source": SOURCE, "asof": asof, "items": dict(self.items)}

    def monthly_for(self, tickers: list[str]) -> dict[str, pd.Series] | None:
        """Return cached monthly closes, or None if any is missing.

        No I/O.
        """
        return (
            {t: self.monthly[t] for t in tickers}
            if all(t in self.monthly for t in tickers)
            else None
        )

    def _fresh(self) -> bool:
        return self.asof is not None and self.clock() - self.asof < self.ttl

    async def refresh(self) -> None:
        """Fetch a new snapshot unless the cache is fresh."""
        async with self._lock:
            if self._fresh():
                return
            self._last_attempt = self.clock()
            try:
                new, new_monthly = await asyncio.to_thread(self.fetcher)
            except Exception as e:  # keep serving the last good snapshot
                logger.warning("market refresh failed: %s: %s", type(e).__name__, str(e)[:200])
                return
            if new:  # merge so one flaky ticker doesn't wipe the others
                self.items.update(new)
                self.monthly.update(new_monthly)
                self.asof = self.clock()

    def kick(self) -> None:
        """Start a background refresh.

        Does nothing while one is running or right after a failed try.
        """
        if self._task and not self._task.done():
            return
        if self.clock() - self._last_attempt < RETRY_AFTER_FAILURE_S:
            return
        self._task = asyncio.create_task(self.refresh())

    async def get(self, wait_first_load: bool = True) -> dict[str, Any]:
        """Return the snapshot; wait up to 25 s for the first load."""
        if self._fresh():
            return self.snapshot()
        if self.asof is None and wait_first_load:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self.refresh(), timeout=25)
        else:
            self.kick()
        return self.snapshot()
