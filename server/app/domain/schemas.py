from typing import Literal, get_args

from pydantic import BaseModel, Field

Bucket = Literal["emergency", "stocks", "single", "bonds", "cash", "alt"]
Goal = Literal["wealth", "house", "business", "income"]
Horizon = Literal[1, 3, 7, 12]  # representative years for each range
Emergency = Literal["none", "insufficient", "enough"]
Debt = Literal["none", "some", "significant"]
Risk = Literal[1, 2, 3]
ProductGroup = Literal["Global Stocks (ETF)", "Individual Stocks", "Bonds", "Savings"]

BUCKETS: list[str] = list(get_args(Bucket))
PROFILE_FIELDS = ["amount", "goal", "horizon", "emergency", "risk", "debt"]

# Percent per bucket. Plain dict inside the domain, validated model at
# the edges.
Pct = dict[str, int]


class Profile(BaseModel):
    """The client's situation, as answered in the profile form."""

    amount: float = Field(ge=0, le=100_000_000)
    goal: Goal
    horizon: Horizon
    emergency: Emergency
    risk: Risk
    debt: Debt


class PctModel(BaseModel):
    """Percent per bucket, validated at the API edge."""

    emergency: int
    stocks: int
    single: int
    bonds: int
    cash: int
    alt: int


class Product(BaseModel):
    """One catalog product (fund, ETF or savings account)."""

    name: str
    ticker: str
    risk: int
    fee: str
    min: str
    blurb: str
    region: str = ""  # where it invests, e.g. "US", "Worldwide"
    # Market-data symbol when it differs from the ticker; `live=False`
    # for accounts and funds with no listing.
    symbol: str | None = None
    live: bool = True
    domain: str | None = None  # issuer website, used for its logo
