from typing import Literal, get_args

from pydantic import BaseModel, Field

Bucket = Literal["emergency", "stocks", "bonds", "cash", "alt"]
Goal = Literal["wealth", "house", "business", "income"]
Horizon = Literal[1, 3, 7, 12]  # representative years for each range
Emergency = Literal["none", "insufficient", "enough"]
Debt = Literal["none", "some", "significant"]
Risk = Literal[1, 2, 3]
ProductGroup = Literal["Global Stocks (ETF)", "Bonds", "Savings"]

BUCKETS: list[str] = list(get_args(Bucket))
PROFILE_FIELDS = ["amount", "goal", "horizon", "emergency", "risk", "debt"]

# Percent per bucket. Plain dict inside the domain, validated model at the edges.
Pct = dict[str, int]


class Profile(BaseModel):
    amount: float = Field(ge=0, le=100_000_000)
    goal: Goal
    horizon: Horizon
    emergency: Emergency
    risk: Risk
    debt: Debt


class PctModel(BaseModel):
    emergency: int
    stocks: int
    bonds: int
    cash: int
    alt: int


class Product(BaseModel):
    name: str
    ticker: str
    risk: int
    fee: str
    min: str
    blurb: str
    region: str = ""  # where it invests, e.g. "US", "Worldwide"
    # Market-data symbol when it differs from the ticker; `live=False` for accounts/funds with no listing.
    symbol: str | None = None
    live: bool = True
