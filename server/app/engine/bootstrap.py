"""Range of outcomes by moving block bootstrap of historical returns.

We resample overlapping 12-month blocks of the portfolio's own monthly
history (Künsch 1989) and stitch them into thousands of paths. Keeping
a year's sequence intact preserves short-run patterns such as runs of
bad months, which resampling single months would break. The result is
a spread of what could happen, not a forecast; it is never called a
backtest. Method and sources: docs/methodology.md.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from app.core.types import AssetClass

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class OutcomeRange:
    """Portfolio value at each year end: bad, typical and good cases."""

    years: tuple[int, ...]
    p10: tuple[float, ...]
    p50: tuple[float, ...]
    p90: tuple[float, ...]
    paid_in: tuple[float, ...]
    prob_loss_year1: float
    prob_reach_goal: float | None


def portfolio_returns(
    class_weights: Mapping[AssetClass, float],
    series: Mapping[AssetClass, Sequence[float]],
    fee_pct: float,
) -> FloatArray:
    """Return the portfolio's monthly returns after its yearly fee.

    Weights are percent per asset class and are rebalanced monthly,
    which matches holding the model portfolio.
    """
    total = sum(class_weights.values())
    months = len(next(iter(series.values())))
    out = np.zeros(months)
    for asset, w in class_weights.items():
        out += (w / total) * np.asarray(series[asset], dtype=np.float64)
    return out - fee_pct / 100 / 12


def block_paths(
    monthly: FloatArray, months: int, n_paths: int, block_months: int, seed: int
) -> FloatArray:
    """Return resampled monthly returns, shape (n_paths, months)."""
    if len(monthly) < block_months:
        raise ValueError("history is shorter than one block")
    rng = np.random.default_rng(seed)
    n_blocks = math.ceil(months / block_months)
    starts = rng.integers(0, len(monthly) - block_months + 1, size=(n_paths, n_blocks))
    idx = (starts[:, :, None] + np.arange(block_months)).reshape(n_paths, -1)[:, :months]
    paths: FloatArray = monthly[idx]
    return paths


def project_outcomes(  # noqa: PLR0913 (inputs plus simulation settings)
    monthly: FloatArray,
    *,
    lump_sum_usd: float,
    monthly_usd: float,
    years: int,
    goal_usd: float | None = None,
    n_paths: int = 5000,
    block_months: int = 12,
    seed: int = 20260420,
) -> OutcomeRange:
    """Return the 10th, 50th and 90th percentile value at each year end.

    The lump sum is invested at the start; each monthly amount is added
    at the end of its month. "Loss in year 1" means ending the first
    year below the money paid in.
    """
    if years < 1:
        raise ValueError("years must be at least 1")
    paths = block_paths(monthly, years * 12, n_paths, block_months, seed)
    value = np.full(n_paths, lump_sum_usd, dtype=np.float64)
    year_ends = [value.copy()]
    for m in range(years * 12):
        value = value * (1 + paths[:, m]) + monthly_usd
        if (m + 1) % 12 == 0:
            year_ends.append(value.copy())
    ends = np.stack(year_ends)  # (years + 1, n_paths)
    p10, p50, p90 = np.percentile(ends, [10, 50, 90], axis=1)
    paid_in = [lump_sum_usd + monthly_usd * 12 * y for y in range(years + 1)]
    return OutcomeRange(
        years=tuple(range(years + 1)),
        p10=tuple(round(float(v), 2) for v in p10),
        p50=tuple(round(float(v), 2) for v in p50),
        p90=tuple(round(float(v), 2) for v in p90),
        paid_in=tuple(paid_in),
        prob_loss_year1=float(np.mean(ends[1] < paid_in[1])),
        prob_reach_goal=None if goal_usd is None else float(np.mean(ends[-1] >= goal_usd)),
    )
