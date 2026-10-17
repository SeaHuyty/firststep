"""Should this person invest yet? (READY-01, READY-02)."""

from collections.abc import Sequence
from dataclasses import dataclass

READY_01 = "READY-01"
READY_02 = "READY-02"


@dataclass(frozen=True, slots=True)
class DebtLine:
    """One debt: what it is, what is owed and its yearly rate."""

    kind: str
    balance_usd: float
    apr_pct: float


@dataclass(frozen=True, slots=True)
class Readiness:
    """Result of the money health check."""

    ready: bool
    emergency_months: float
    high_apr_debts: tuple[DebtLine, ...]
    investable_monthly_usd: float
    failed_rule_ids: tuple[str, ...]


def assess_readiness(
    *,
    monthly_income_usd: float,
    monthly_expenses_usd: float,
    liquid_savings_usd: float,
    debts: Sequence[DebtLine],
    min_emergency_months: float,
    max_apr_pct: float,
) -> Readiness:
    """Return whether the emergency fund and debt checks pass.

    Emergency months are savings divided by monthly costs; with no
    costs, any savings count as a full cushion. A debt fails READY-02
    when its rate is strictly above the limit.
    """
    if monthly_expenses_usd > 0:
        months = liquid_savings_usd / monthly_expenses_usd
    else:
        months = float("inf") if liquid_savings_usd > 0 else 0.0
    expensive = tuple(d for d in debts if d.balance_usd > 0 and d.apr_pct > max_apr_pct)
    failed = tuple(
        rule
        for rule, broken in (
            (READY_01, months < min_emergency_months),
            (READY_02, bool(expensive)),
        )
        if broken
    )
    return Readiness(
        ready=not failed,
        emergency_months=months,
        high_apr_debts=expensive,
        investable_monthly_usd=max(0.0, monthly_income_usd - monthly_expenses_usd),
        failed_rule_ids=failed,
    )
