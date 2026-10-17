from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.core.reference import ModelPortfolio, Reference, RuleBook, load_reference
from app.core.settings import Settings
from app.core.types import EQUITY_CLASSES, AssetClass, ClientClass, RiskRating, to_money

DATA_DIR = Settings(_env_file=None).data_dir


@pytest.fixture(scope="module")
def ref() -> Reference:
    return load_reference(DATA_DIR)


def test_all_reference_files_load(ref: Reference) -> None:
    assert len(ref.products) >= 12
    assert set(ref.portfolios) == set(ClientClass)
    assert len(ref.questionnaire.questions) == 13
    assert set(ref.personas.personas) == {"amina", "leo", "mei"}


@pytest.mark.parametrize("client_class", list(ClientClass))
def test_model_portfolio_passes_suit_01_for_its_class(
    ref: Reference, client_class: ClientClass
) -> None:
    limit = ref.rules.suit_01.max_rating_for_class[client_class]
    for product_id in ref.portfolios[client_class].weights:
        assert ref.products[product_id].risk_rating <= limit, product_id


@pytest.mark.parametrize("client_class", list(ClientClass))
def test_model_portfolio_passes_conc_01_for_its_class(
    ref: Reference, client_class: ClientClass
) -> None:
    rule = ref.rules.conc_01
    weights = ref.portfolios[client_class].weights
    assert max(weights.values()) <= rule.max_product_pct
    if client_class in rule.exempt_classes:
        return
    by_class: dict[AssetClass, float] = {}
    for product_id, w in weights.items():
        asset = ref.products[product_id].asset_class
        by_class[asset] = by_class.get(asset, 0) + w
    assert all(w <= rule.max_equity_class_pct for a, w in by_class.items() if a in EQUITY_CLASSES)


def test_equity_share_rises_with_client_class(ref: Reference) -> None:
    def equity(c: ClientClass) -> float:
        weights = ref.portfolios[c].weights
        return sum(w for p, w in weights.items() if ref.products[p].asset_class in EQUITY_CLASSES)

    shares = [equity(c) for c in ClientClass]
    assert shares == sorted(shares)
    assert shares[0] == 0  # C1 holds only R1 funds


def test_returns_cover_2000_to_2025_without_gaps(ref: Reference) -> None:
    months = ref.returns.months
    assert months[0] == "2000-01"
    assert months[-1] == "2025-12"
    assert len(months) == 26 * 12
    for series in ref.returns.series.values():
        assert len(series) == len(months)
        assert all(-0.5 < r < 0.5 for r in series)


def test_returns_include_the_march_2020_crash(ref: Reference) -> None:
    i = ref.returns.index_of("2020-03")
    assert ref.returns.series[AssetClass.US_EQUITY][i] < -0.10
    assert ref.returns.series[AssetClass.BONDS][i] > 0  # bonds rose as yields fell


def test_every_product_tracks_a_known_asset_class(ref: Reference) -> None:
    assert {p.asset_class for p in ref.products.values()} <= set(ref.returns.series)


def test_tier_2_tools_are_the_execution_tools(ref: Reference) -> None:
    tier_2 = {tool for tool, tier in ref.rules.tiers.tier_of.items() if tier == 2}
    assert tier_2 == {"place_order"}


def test_scored_questions_have_a_score_on_every_option(ref: Reference) -> None:
    for q in ref.questionnaire.questions:
        if q.scale is not None:
            assert q.options, q.id
            assert all(o.score is not None for o in q.options), q.id


def test_persona_answers_match_question_ids(ref: Reference) -> None:
    ids = {q.id for q in ref.questionnaire.questions}
    for persona in ref.personas.personas.values():
        assert set(persona.answers) <= ids


def test_portfolio_weights_must_sum_to_100() -> None:
    with pytest.raises(ValidationError, match="sum to 90"):
        ModelPortfolio(label="x", summary="x", weights={"MMF01": 90})


def test_stage_tool_without_a_tier_is_rejected(tmp_path: Path) -> None:
    raw = (
        (DATA_DIR / "rules.yaml")
        .read_text()
        .replace("ONBOARD: [answer_question,", "ONBOARD: [delete_everything, answer_question,")
    )

    with pytest.raises(ValidationError, match="delete_everything"):
        RuleBook.model_validate(yaml.safe_load(raw))


def test_unknown_rule_fields_are_rejected() -> None:

    raw = yaml.safe_load((DATA_DIR / "rules.yaml").read_text())
    raw["LIM-01"]["max_order_usd_typo"] = 1
    with pytest.raises(ValidationError, match="max_order_usd_typo"):
        RuleBook.model_validate(raw)


def test_scale_codes_parse_and_print() -> None:
    assert str(ClientClass.C3) == "C3"
    assert str(RiskRating.R4) == "R4"


def test_money_rounds_half_up_to_the_cent() -> None:
    assert to_money("2.345") == Decimal("2.35")
    assert to_money(0.1 + 0.2) == Decimal("0.30")
