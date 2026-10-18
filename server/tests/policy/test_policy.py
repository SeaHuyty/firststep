"""Every rule ID has an allow test and a block test."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.agent.guards import SAFE_FALLBACK
from app.core.reference import Reference, load_reference
from app.core.settings import Settings
from app.core.types import ClientClass, Stage
from app.engine.readiness import DebtLine, assess_readiness
from app.policy.engine import Policy
from app.policy.tokens import TokenSigner, content_hash

NOW = datetime(2026, 10, 17, 10, 0, tzinfo=UTC)
D = Decimal


@pytest.fixture(scope="module")
def ref() -> Reference:
    return load_reference(Settings(_env_file=None).data_dir)


@pytest.fixture(scope="module")
def policy(ref: Reference) -> Policy:
    return Policy(ref, TokenSigner(b"test-secret-at-least-16", timedelta(minutes=10)))


def never_used(_: str) -> bool:
    return False


# STAGE-01


def test_stage_01_allows_a_tool_in_its_stage(policy: Policy) -> None:
    assert policy.stage("assess_readiness", Stage.READINESS).allowed


def test_stage_01_blocks_ordering_before_confirm(policy: Policy) -> None:
    d = policy.stage("place_order", Stage.PROFILE)
    assert (d.allowed, d.rule_id) == (False, "STAGE-01")


def test_stage_01_blocks_investing_tools_in_the_savings_plan(policy: Policy) -> None:
    for tool in ("propose_allocation", "prepare_orders", "place_order"):
        assert not policy.stage(tool, Stage.SAVINGS_PLAN).allowed


# READY-01, READY-02


def readiness(savings: float, debts: list[DebtLine]):
    return assess_readiness(
        monthly_income_usd=3800,
        monthly_expenses_usd=2300,
        liquid_savings_usd=savings,
        debts=debts,
        min_emergency_months=3,
        max_apr_pct=8,
    )


def test_ready_01_allows_a_full_cushion(policy: Policy) -> None:
    assert policy.readiness(readiness(15000, [])).allowed


def test_ready_01_blocks_a_thin_cushion(policy: Policy) -> None:
    d = policy.readiness(readiness(1000, []))
    assert (d.allowed, d.rule_id) == (False, "READY-01")
    assert "0.4 months" in d.message


def test_ready_02_allows_a_cheap_student_loan(policy: Policy) -> None:
    assert policy.readiness(readiness(15000, [DebtLine("student_loan", 12000, 5.5)])).allowed


def test_ready_02_blocks_card_debt_and_names_the_rate(policy: Policy) -> None:
    d = policy.readiness(readiness(15000, [DebtLine("credit_card", 1750, 22.9)]))
    assert (d.allowed, d.rule_id) == (False, "READY-02")
    assert "credit card charges 22.9% a year" in d.message


def test_ready_02_is_named_before_ready_01(policy: Policy) -> None:
    d = policy.readiness(readiness(600, [DebtLine("credit_card", 1750, 22.9)]))
    assert d.rule_id == "READY-02"


# SUIT-01


def test_suit_01_allows_the_c2_model_portfolio_for_mei(policy: Policy, ref: Reference) -> None:
    assert policy.suitability(ref.portfolios[ClientClass.C2].weights, ClientClass.C2).allowed


def test_suit_01_blocks_all_tech_for_mei(policy: Policy) -> None:
    d = policy.suitability({"TEC01": 100}, ClientClass.C2)
    assert (d.allowed, d.rule_id) == (False, "SUIT-01")
    assert d.message.startswith("Global Technology Fund is rated R4, above your C2 level")


# CONC-01


def test_conc_01_allows_the_c4_model_portfolio(policy: Policy, ref: Reference) -> None:
    assert policy.concentration(ref.portfolios[ClientClass.C4].weights, ClientClass.C4).allowed


def test_conc_01_blocks_everything_in_one_fund(policy: Policy) -> None:
    d = policy.concentration({"TEC01": 100}, ClientClass.C4)
    assert (d.allowed, d.rule_id) == (False, "CONC-01")
    assert "Global Technology Fund would be 100%" in d.message


def test_allocation_reports_suitability_before_concentration(policy: Policy) -> None:
    assert policy.allocation({"TEC01": 100}, ClientClass.C2).rule_id == "SUIT-01"
    assert policy.allocation({"TEC01": 100}, ClientClass.C4).rule_id == "CONC-01"
    assert policy.allocation({"USE01": 30, "GOV01": 35, "STB01": 35}, ClientClass.C3).allowed


# LIM-01


def test_lim_01_allows_orders_within_limits(policy: Policy) -> None:
    assert policy.order_limits([D(6000), D(4000)], spent_today=D(5000)).allowed


def test_lim_01_blocks_one_order_over_10000(policy: Policy) -> None:
    d = policy.order_limits([D("10000.01")], spent_today=D(0))
    assert (d.allowed, d.rule_id) == (False, "LIM-01")
    assert "$10,000 per-order limit" in d.message


def test_lim_01_blocks_passing_the_daily_limit(policy: Policy) -> None:
    d = policy.order_limits([D(6000)], spent_today=D(15000))
    assert (d.allowed, d.rule_id) == (False, "LIM-01")
    assert "$20,000 daily limit" in d.message


# CONF-01

PROPOSAL = {"orders": [{"product_id": "USE01", "side": "buy", "amount": "1800.00"}]}


def mint(policy: Policy, proposal_id: str = "p1") -> tuple[str, str]:
    h = content_hash(PROPOSAL)
    token, claims = policy.signer.mint(proposal_id, h, NOW)
    return token, claims.nonce


def confirm(policy: Policy, token: str | None, *, now: datetime = NOW, used=never_used):
    return policy.confirmation(
        token, proposal_id="p1", contents_sha256=content_hash(PROPOSAL), now=now, nonce_used=used
    )


def test_conf_01_allows_a_fresh_token_for_this_proposal(policy: Policy) -> None:
    token, _ = mint(policy)
    assert confirm(policy, token).allowed


def test_conf_01_blocks_a_missing_token(policy: Policy) -> None:
    d = confirm(policy, None)
    assert (d.allowed, d.rule_id) == (False, "CONF-01")
    assert d.message == "This order needs your confirmation. Press Confirm to go ahead."


def test_conf_01_blocks_a_forged_token(policy: Policy) -> None:
    token, _ = mint(policy)
    body, sig = token.split(".")
    assert not confirm(policy, f"{body}.{sig[:-2]}AA").allowed
    assert not confirm(policy, "not-a-token").allowed


def test_conf_01_blocks_a_token_signed_with_another_key(policy: Policy, ref: Reference) -> None:
    other = TokenSigner(b"some-other-secret-key", timedelta(minutes=10))
    token, _ = other.mint("p1", content_hash(PROPOSAL), NOW)
    assert not confirm(policy, token).allowed


def test_conf_01_blocks_a_token_for_another_proposal(policy: Policy) -> None:
    token, _ = mint(policy, proposal_id="p2")
    assert "different plan" in confirm(policy, token).message


def test_conf_01_blocks_a_changed_proposal(policy: Policy) -> None:
    token, _ = mint(policy)
    changed = {"orders": [{"product_id": "TEC01", "side": "buy", "amount": "1800.00"}]}
    d = policy.confirmation(
        token,
        proposal_id="p1",
        contents_sha256=content_hash(changed),
        now=NOW,
        nonce_used=never_used,
    )
    assert not d.allowed


def test_conf_01_blocks_an_expired_token(policy: Policy) -> None:
    token, _ = mint(policy)
    assert "expired" in confirm(policy, token, now=NOW + timedelta(minutes=10)).message


def test_conf_01_blocks_a_reused_token(policy: Policy) -> None:
    token, nonce = mint(policy)
    assert "already used" in confirm(policy, token, used=lambda n: n == nonce).message


def test_signer_rejects_a_short_secret() -> None:
    with pytest.raises(ValueError, match="16 bytes"):
        TokenSigner(b"short", timedelta(minutes=1))


# COOL-01


def test_cool_01_allows_a_small_sale_in_a_drop(policy: Policy) -> None:
    assert policy.cooling_off(D(100), D(10000), drawdown_pct=30).allowed


def test_cool_01_blocks_a_panic_sale(policy: Policy) -> None:
    d = policy.cooling_off(D(5000), D(10000), drawdown_pct=30)
    assert (d.allowed, d.rule_id) == (False, "COOL-01")
    assert d.message.startswith("This fund is 30% below its high")
    assert "wait 24 hours" in d.message


# LANG-01..04


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        ("This fund is guaranteed to grow.", "LANG-01"),
        ("Bonds are risk-free.", "LANG-02"),
        ("You can't lose with index funds.", "LANG-02"),
        ("Your money will double in 7 years.", "LANG-03"),
        ("Tech stocks are going to rise next year.", "LANG-04"),
    ],
)
def test_lang_rules_block_promises_and_predictions(policy: Policy, text: str, rule: str) -> None:
    assert rule in policy.language(text)


def test_lang_rules_allow_honest_range_language(policy: Policy) -> None:
    text = (
        "After 10 years: about $47,000 in a bad case, $59,000 typically, $72,000 in a good "
        "case. This is a range of outcomes from past markets, not a prediction."
    )
    assert policy.language(text) == []


def test_the_safe_fallback_passes_the_lang_rules(policy: Policy) -> None:
    assert policy.language(SAFE_FALLBACK) == []
