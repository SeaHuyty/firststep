"""The plan Sprout offers instead of a portfolio when it says "not yet".

Order of steps, from the guidance cited in docs/methodology.md: keep a
small cash buffer, pay the highest-rate debt first (the "avalanche",
which costs the least interest), then build the emergency fund.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.engine.readiness import DebtLine

MAX_MONTHS = 600  # a plan that takes over 50 years is reported as unreachable

Action = Literal["save_buffer", "pay_debt", "build_emergency_fund"]


@dataclass(frozen=True, slots=True)
class PlanStep:
    """One step: what to do, how much a month, for how long."""

    action: Action
    monthly_usd: float
    months: int
    target_usd: float
    debt_kind: str | None = None
    interest_usd: float = 0.0


@dataclass(frozen=True, slots=True)
class SavingsPlan:
    """Steps in order, and the total months until ready."""

    steps: tuple[PlanStep, ...]
    months_to_ready: int | None  # None when the surplus is zero or too small


def _months_to_save(gap_usd: float, monthly_usd: float) -> int:
    return math.ceil(gap_usd / monthly_usd - 1e-9) if gap_usd > 0 else 0


def _payoff(balance_usd: float, apr_pct: float, monthly_usd: float) -> tuple[int, float] | None:
    """Return (months, interest) to clear a debt, or None if never."""
    rate = apr_pct / 100 / 12
    months, interest = 0, 0.0
    while balance_usd > 1e-9:
        charge = balance_usd * rate
        if monthly_usd <= charge or months >= MAX_MONTHS:
            return None
        interest += charge
        balance_usd = balance_usd + charge - monthly_usd
        months += 1
    return months, interest


def build_savings_plan(
    *,
    monthly_surplus_usd: float,
    liquid_savings_usd: float,
    monthly_expenses_usd: float,
    expensive_debts: Sequence[DebtLine],
    min_emergency_months: float,
    starter_buffer_usd: float,
) -> SavingsPlan:
    """Return the steps that make someone ready to invest.

    The whole monthly surplus goes to one step at a time. Interest on a
    debt accrues monthly at APR / 12 while it is being paid.
    """
    if monthly_surplus_usd <= 0:
        return SavingsPlan(steps=(), months_to_ready=None)

    steps: list[PlanStep] = []
    buffer = min(starter_buffer_usd, monthly_expenses_usd * min_emergency_months)
    savings = liquid_savings_usd
    if expensive_debts and savings < buffer:
        months = _months_to_save(buffer - savings, monthly_surplus_usd)
        steps.append(PlanStep("save_buffer", monthly_surplus_usd, months, buffer))
        savings = buffer

    for debt in sorted(expensive_debts, key=lambda d: d.apr_pct, reverse=True):
        result = _payoff(debt.balance_usd, debt.apr_pct, monthly_surplus_usd)
        if result is None:
            return SavingsPlan(steps=tuple(steps), months_to_ready=None)
        months, interest = result
        steps.append(
            PlanStep(
                "pay_debt",
                monthly_surplus_usd,
                months,
                debt.balance_usd,
                debt_kind=debt.kind,
                interest_usd=round(interest, 2),
            )
        )

    target = monthly_expenses_usd * min_emergency_months
    if savings < target:
        months = _months_to_save(target - savings, monthly_surplus_usd)
        steps.append(PlanStep("build_emergency_fund", monthly_surplus_usd, months, target))

    return SavingsPlan(steps=tuple(steps), months_to_ready=sum(s.months for s in steps))
