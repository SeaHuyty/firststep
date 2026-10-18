"""Closed sets and the money type shared by every layer.

One home per concept (standards/backend.md section 3): the client and
product risk scales, asset classes, stages, tiers and order sides are
defined here and nowhere else.
"""

from decimal import ROUND_HALF_UP, Decimal
from enum import IntEnum, StrEnum
from typing import Annotated

from pydantic import BeforeValidator, PlainSerializer

Money = Decimal
"""Cash, order amounts and fills in the paper account."""

CENT = Decimal("0.01")


def to_money(value: Decimal | float | int | str) -> Money:
    """Return a value as Decimal dollars rounded half up to the cent."""
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


class ClientClass(IntEnum):
    """Investor risk class, C1 (most cautious) to C5.

    The C1–C5 / R1–R5 grading follows the practice under the CSRC
    investor suitability Measures (see docs/research/methodology.md).
    """

    C1 = 1
    C2 = 2
    C3 = 3
    C4 = 4
    C5 = 5

    def __str__(self) -> str:
        """Return the code, e.g. "C3"."""
        return self.name


class RiskRating(IntEnum):
    """Product risk rating, R1 (lowest) to R5."""

    R1 = 1
    R2 = 2
    R3 = 3
    R4 = 4
    R5 = 5

    def __str__(self) -> str:
        """Return the code, e.g. "R3"."""
        return self.name


def _parse_scale(cls: type[IntEnum]) -> BeforeValidator:
    """Return a validator accepting "C3", 3 or the enum itself."""

    def parse(value: object) -> object:
        if isinstance(value, str) and value[:1].upper() == cls.__name__[0]:
            return cls[value.upper()]
        return value

    return BeforeValidator(parse)


ClientClassField = Annotated[
    ClientClass, _parse_scale(ClientClass), PlainSerializer(str, return_type=str)
]
RiskRatingField = Annotated[
    RiskRating, _parse_scale(RiskRating), PlainSerializer(str, return_type=str)
]


class AssetClass(StrEnum):
    """Asset classes with a monthly series in data/returns.csv."""

    CASH = "cash"
    SHORT_BONDS = "short_bonds"
    BONDS = "bonds"
    US_EQUITY = "us_equity"
    INTL_EQUITY = "intl_equity"
    EM_EQUITY = "em_equity"
    US_TECH = "us_tech"
    GOLD = "gold"


EQUITY_CLASSES = frozenset(
    {AssetClass.US_EQUITY, AssetClass.INTL_EQUITY, AssetClass.EM_EQUITY, AssetClass.US_TECH}
)


class Family(StrEnum):
    """The four families a beginner sees in the allocation donut."""

    CASH = "cash"
    BONDS = "bonds"
    STOCKS = "stocks"
    GOLD = "gold"


FAMILY_OF: dict[AssetClass, Family] = {
    AssetClass.CASH: Family.CASH,
    AssetClass.SHORT_BONDS: Family.BONDS,
    AssetClass.BONDS: Family.BONDS,
    AssetClass.US_EQUITY: Family.STOCKS,
    AssetClass.INTL_EQUITY: Family.STOCKS,
    AssetClass.EM_EQUITY: Family.STOCKS,
    AssetClass.US_TECH: Family.STOCKS,
    AssetClass.GOLD: Family.GOLD,
}


class Stage(StrEnum):
    """Session stages; each stage exposes only its own tools."""

    ONBOARD = "ONBOARD"
    READINESS = "READINESS"
    SAVINGS_PLAN = "SAVINGS_PLAN"
    PROFILE = "PROFILE"
    GOAL = "GOAL"
    PROPOSE = "PROPOSE"
    CONFIRM = "CONFIRM"
    EXECUTED = "EXECUTED"
    MONITOR = "MONITOR"


class Tier(IntEnum):
    """Permission tier of a tool (security self-assessment)."""

    READ = 0
    PROPOSE = 1
    EXECUTE = 2
    SENSITIVE = 3


class Side(StrEnum):
    """Order side."""

    BUY = "buy"
    SELL = "sell"


class IncomeStability(StrEnum):
    """How steady the client's income is."""

    STABLE = "stable"
    VARIABLE = "variable"
    NONE = "none"
