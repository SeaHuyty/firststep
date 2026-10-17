"""Which products a client may hold (SUIT-01) and CONC-01 limits."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol, TypeVar

from app.core.types import EQUITY_CLASSES, AssetClass, ClientClass, RiskRating

SUIT_01 = "SUIT-01"
CONC_01 = "CONC-01"


class Fund(Protocol):
    """What the engine needs to know about a product."""

    @property
    def id(self) -> str:
        """Product id."""

    @property
    def asset_class(self) -> AssetClass:
        """The asset class it tracks."""

    @property
    def risk_rating(self) -> RiskRating:
        """R1-R5."""

    @property
    def ter_pct(self) -> float:
        """Yearly fee, percent."""


F = TypeVar("F", bound=Fund)


@dataclass(frozen=True, slots=True)
class Violation:
    """One broken rule, with what broke it."""

    rule_id: str
    subject: str  # a product id or an asset class
    value_pct: float
    limit_pct: float


def is_suitable(
    rating: RiskRating, client: ClientClass, matrix: Mapping[ClientClass, RiskRating]
) -> bool:
    """Return whether a product rating fits a client class (SUIT-01)."""
    return rating <= matrix[client]


def suitable_funds(
    funds: Iterable[F], client: ClientClass, matrix: Mapping[ClientClass, RiskRating]
) -> tuple[list[F], int]:
    """Return the suitable funds and how many were left out."""
    keep, dropped = [], 0
    for fund in funds:
        if is_suitable(fund.risk_rating, client, matrix):
            keep.append(fund)
        else:
            dropped += 1
    return keep, dropped


def unsuitable_lines(
    weights: Mapping[str, float],
    funds: Mapping[str, Fund],
    client: ClientClass,
    matrix: Mapping[ClientClass, RiskRating],
) -> list[Violation]:
    """Return a SUIT-01 violation per held product above the class."""
    limit = matrix[client]
    return [
        Violation(SUIT_01, pid, float(funds[pid].risk_rating), float(limit))
        for pid, w in weights.items()
        if w > 0 and not is_suitable(funds[pid].risk_rating, client, matrix)
    ]


def weights_by_class(
    weights: Mapping[str, float], funds: Mapping[str, Fund]
) -> dict[AssetClass, float]:
    """Return portfolio percent per asset class."""
    out: dict[AssetClass, float] = {}
    for pid, w in weights.items():
        asset = funds[pid].asset_class
        out[asset] = out.get(asset, 0.0) + w
    return out


def concentration_violations(
    weights: Mapping[str, float],
    funds: Mapping[str, Fund],
    client: ClientClass,
    *,
    max_product_pct: float,
    max_equity_class_pct: float,
    exempt: Iterable[ClientClass],
) -> list[Violation]:
    """Return CONC-01 violations: a product or equity class too big."""
    if client in set(exempt):
        return []
    found = [
        Violation(CONC_01, pid, w, max_product_pct)
        for pid, w in weights.items()
        if w > max_product_pct
    ]
    found += [
        Violation(CONC_01, str(asset), w, max_equity_class_pct)
        for asset, w in weights_by_class(weights, funds).items()
        if asset in EQUITY_CLASSES and w > max_equity_class_pct
    ]
    return found


def weighted_fee_pct(weights: Mapping[str, float], funds: Mapping[str, Fund]) -> float:
    """Return the portfolio's yearly fee in percent, by holding."""
    return sum(w / 100 * funds[pid].ter_pct for pid, w in weights.items())
