"""Turn target weights into dollar amounts that add up to the cent."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal

from app.core.types import CENT, FAMILY_OF, Family, Money, to_money
from app.engine.suitability import Fund, weights_by_class


@dataclass(frozen=True, slots=True)
class Line:
    """One product in a proposal."""

    product_id: str
    weight_pct: float
    amount_usd: Money


def split_amount(weights: Mapping[str, float], total_usd: Money) -> tuple[Line, ...]:
    """Return one line per product; amounts sum exactly to the total.

    Each amount is rounded down to the cent, then the leftover cents go
    to the largest remainders (Hamilton's method), so no money is
    created or lost by rounding.
    """
    total_w = sum(weights.values())
    if total_w <= 0:
        raise ValueError("weights must be positive")
    total_usd = to_money(total_usd)
    exact = {
        pid: total_usd * Decimal(str(w)) / Decimal(str(total_w)) for pid, w in weights.items()
    }
    floored = {pid: v.quantize(CENT, rounding=ROUND_FLOOR) for pid, v in exact.items()}
    leftover = int((total_usd - sum(floored.values())) / CENT)
    # Largest remainder first; ties go to the first id, so results are
    # stable across runs.
    by_remainder = sorted(weights, key=lambda pid: (floored[pid] - exact[pid], pid))
    for pid in by_remainder[:leftover]:
        floored[pid] += CENT
    return tuple(Line(pid, weights[pid], floored[pid]) for pid in weights if weights[pid] > 0)


def family_split(weights: Mapping[str, float], funds: Mapping[str, Fund]) -> dict[Family, float]:
    """Return percent per family (cash, bonds, stocks, gold)."""
    out = dict.fromkeys(Family, 0.0)
    for asset, w in weights_by_class(weights, funds).items():
        out[FAMILY_OF[asset]] += w
    return out
