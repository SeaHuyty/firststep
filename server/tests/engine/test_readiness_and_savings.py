import pytest

from app.engine.readiness import READY_01, READY_02, DebtLine, assess_readiness
from app.engine.savings import build_savings_plan

CARD = DebtLine("credit_card", 1750, 22.9)
STUDENT_LOAN = DebtLine("student_loan", 12000, 5.5)


def check(income: float, costs: float, savings: float, debts: list[DebtLine]):
    return assess_readiness(
        monthly_income_usd=income,
        monthly_expenses_usd=costs,
        liquid_savings_usd=savings,
        debts=debts,
        min_emergency_months=3,
        max_apr_pct=8,
    )


@pytest.mark.parametrize(
    ("savings", "debts", "failed"),
    [
        (15000, [STUDENT_LOAN], ()),  # Leo: 6.5 months, cheap loan
        (600, [CARD], (READY_01, READY_02)),  # Amina
        (600, [], (READY_01,)),
        (9000, [CARD], (READY_02,)),
    ],
)
def test_readiness_rules(savings: float, debts: list[DebtLine], failed: tuple[str, ...]) -> None:
    result = check(3800, 2300, savings, debts)
    assert result.failed_rule_ids == failed
    assert result.ready is (not failed)


def test_ready_01_allows_exactly_three_months() -> None:
    assert check(3000, 2000, 6000, []).ready


def test_ready_01_blocks_just_under_three_months() -> None:
    assert check(3000, 2000, 5999, []).failed_rule_ids == (READY_01,)


def test_ready_02_allows_debt_at_the_limit() -> None:
    assert check(3000, 2000, 9000, [DebtLine("car", 5000, 8.0)]).ready


def test_ready_02_blocks_debt_above_the_limit() -> None:
    result = check(3000, 2000, 9000, [DebtLine("car", 5000, 8.01)])
    assert result.failed_rule_ids == (READY_02,)
    assert result.high_apr_debts == (DebtLine("car", 5000, 8.01),)


def test_paid_off_expensive_debt_does_not_block() -> None:
    assert check(3000, 2000, 9000, [DebtLine("card", 0, 25)]).ready


def test_investable_amount_is_never_negative() -> None:
    assert check(1000, 1500, 9000, []).investable_monthly_usd == 0


def test_no_costs_and_some_savings_is_a_full_cushion() -> None:
    assert check(1000, 0, 1, []).ready


def plan(surplus: float, savings: float, debts: list[DebtLine]):
    return build_savings_plan(
        monthly_surplus_usd=surplus,
        liquid_savings_usd=savings,
        monthly_expenses_usd=1150,
        expensive_debts=debts,
        min_emergency_months=3,
        starter_buffer_usd=1000,
    )


def test_amina_gets_buffer_then_card_then_emergency_fund() -> None:
    result = plan(250, 600, [CARD])
    assert [s.action for s in result.steps] == ["save_buffer", "pay_debt", "build_emergency_fund"]
    buffer, card, fund = result.steps
    assert buffer.months == 2  # $400 at $250 a month
    assert card.months == 8
    assert card.interest_usd == pytest.approx(146.9, abs=0.1)  # amortised by hand
    assert fund.target_usd == 3450
    assert fund.months == 10  # $2,450 at $250 a month
    assert result.months_to_ready == 20


def test_highest_rate_debt_is_paid_first() -> None:
    result = plan(400, 5000, [DebtLine("loan", 900, 12), DebtLine("card", 900, 24)])
    kinds = [s.debt_kind for s in result.steps if s.action == "pay_debt"]
    assert kinds == ["card", "loan"]


def test_no_surplus_means_no_date() -> None:
    result = plan(0, 600, [CARD])
    assert result.months_to_ready is None
    assert result.steps == ()


def test_payment_below_interest_is_unreachable() -> None:
    result = plan(10, 1000, [DebtLine("card", 50000, 30)])
    assert result.months_to_ready is None


def test_emergency_fund_only_when_no_debt() -> None:
    result = plan(500, 2000, [])
    assert [s.action for s in result.steps] == ["build_emergency_fund"]
    assert result.months_to_ready == 3  # $1,450 at $500
