"""What Sprout knows about one client, stored with their session.

Only the fields the advice needs are kept (no name, no ID numbers),
in line with data minimisation in the security design.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.core.types import ClientClassField, IncomeStability


class Debt(BaseModel):
    """One debt the client owes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str = Field(max_length=40)
    balance_usd: float = Field(ge=0, le=10_000_000)
    apr_pct: float = Field(ge=0, le=100)


class Goal(BaseModel):
    """What the client is investing for."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(max_length=60)
    target_usd: float = Field(gt=0, le=100_000_000)
    horizon_years: float = Field(gt=0, le=60)
    lump_sum_usd: float = Field(ge=0, le=10_000_000)
    monthly_usd: float = Field(ge=0, le=1_000_000)


class RiskResult(BaseModel):
    """The scored profile, as shown on the risk badge."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tolerance: int = Field(ge=1, le=5)
    capacity: int = Field(ge=1, le=5)
    horizon_cap: ClientClassField | None = None
    final_class: ClientClassField
    limited_by: str


class Profile(BaseModel):
    """Everything collected so far; missing fields are None."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    age: int | None = Field(default=None, ge=18, le=100)
    monthly_income_usd: float | None = Field(default=None, ge=0, le=10_000_000)
    monthly_expenses_usd: float | None = Field(default=None, ge=0, le=10_000_000)
    liquid_savings_usd: float | None = Field(default=None, ge=0, le=100_000_000)
    debts: tuple[Debt, ...] | None = None
    income_stability: IncomeStability | None = None
    dependants: int | None = Field(default=None, ge=0, le=20)
    loss_capacity: int | None = Field(default=None, ge=1, le=5)
    tolerance_answers: dict[str, int] = Field(default_factory=dict)
    risk: RiskResult | None = None
    goal: Goal | None = None
