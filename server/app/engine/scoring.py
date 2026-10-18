"""Risk profile: tolerance and capacity, the lower one wins (C1-C5).

Tolerance (willingness) is the mean of the situational answers;
capacity (ability to bear losses) is its weakest component; the
horizon caps both (HOR-01). Method and sources:
docs/research/methodology.md.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.core.types import ClientClass

HOR_01 = "HOR-01"

LimitedBy = Literal["tolerance", "capacity", "horizon"]


@dataclass(frozen=True, slots=True)
class AgeBandScore:
    """Capacity score for ages below `under`."""

    under: int
    score: int


@dataclass(frozen=True, slots=True)
class HorizonBand:
    """Goals shorter than `under_years` are capped at `max_class`."""

    under_years: float
    max_class: ClientClass


@dataclass(frozen=True, slots=True)
class RiskProfile:
    """The two scores, the horizon cap and the final class."""

    tolerance: int
    capacity: int
    horizon_cap: ClientClass | None
    final_class: ClientClass
    limited_by: LimitedBy


def _round_half_up(x: float) -> int:
    return math.floor(x + 0.5)


def tolerance_score(answers: Sequence[int]) -> int:
    """Return the 1-5 tolerance: the mean answer, rounded half up."""
    if not answers or any(not 1 <= a <= 5 for a in answers):
        raise ValueError("tolerance needs at least one answer, each 1-5")
    return _round_half_up(sum(answers) / len(answers))


def age_score(age: int, bands: Sequence[AgeBandScore]) -> int:
    """Return the capacity score of the first band covering an age."""
    for band in sorted(bands, key=lambda b: b.under):
        if age < band.under:
            return band.score
    raise ValueError(f"no age band covers {age}")


def capacity_score(component_scores: Sequence[int]) -> int:
    """Return the 1-5 capacity score: the weakest component."""
    if not component_scores or any(not 1 <= s <= 5 for s in component_scores):
        raise ValueError("capacity needs at least one score, each 1-5")
    return min(component_scores)


def horizon_cap(horizon_years: float, bands: Sequence[HorizonBand]) -> ClientClass | None:
    """Return the class cap for a goal's horizon, or None."""
    for band in sorted(bands, key=lambda b: b.under_years):
        if horizon_years < band.under_years:
            return band.max_class
    return None


def risk_profile(tolerance: int, capacity: int, cap: ClientClass | None) -> RiskProfile:
    """Return the final class: lowest of tolerance, capacity and cap.

    `limited_by` names what set the class, so the "Why?" card can say
    it; on a tie, the horizon, then capacity, is named first.
    """
    candidates: list[tuple[int, LimitedBy]] = [(tolerance, "tolerance"), (capacity, "capacity")]
    if cap is not None:
        candidates.append((int(cap), "horizon"))
    final = min(value for value, _ in candidates)
    order: dict[LimitedBy, int] = {"horizon": 0, "capacity": 1, "tolerance": 2}
    limited_by = min((name for value, name in candidates if value == final), key=order.__getitem__)
    return RiskProfile(
        tolerance=tolerance,
        capacity=capacity,
        horizon_cap=cap,
        final_class=ClientClass(final),
        limited_by=limited_by,
    )
