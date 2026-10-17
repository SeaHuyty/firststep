from dataclasses import dataclass
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.core.types import AssetClass, ClientClass, Family, RiskRating
from app.engine.allocation import family_split, split_amount
from app.engine.suitability import (
    CONC_01,
    SUIT_01,
    concentration_violations,
    is_suitable,
    suitable_funds,
    unsuitable_lines,
    weighted_fee_pct,
)

MATRIX = {c: RiskRating(int(c)) for c in ClientClass}


@dataclass(frozen=True)
class F:
    id: str
    asset_class: AssetClass
    risk_rating: RiskRating
    ter_pct: float


FUNDS = {
    "MMF": F("MMF", AssetClass.CASH, RiskRating.R1, 0.10),
    "GOV": F("GOV", AssetClass.BONDS, RiskRating.R2, 0.05),
    "USE": F("USE", AssetClass.US_EQUITY, RiskRating.R3, 0.04),
    "USE2": F("USE2", AssetClass.US_EQUITY, RiskRating.R3, 0.03),
    "TEC": F("TEC", AssetClass.US_TECH, RiskRating.R4, 0.45),
}


@pytest.mark.parametrize("client", list(ClientClass))
@pytest.mark.parametrize("rating", list(RiskRating))
def test_suit_01_matrix(client: ClientClass, rating: RiskRating) -> None:
    assert is_suitable(rating, client, MATRIX) is (rating <= client)


def test_suit_01_filters_the_shelf_for_c2() -> None:
    keep, dropped = suitable_funds(FUNDS.values(), ClientClass.C2, MATRIX)
    assert [f.id for f in keep] == ["MMF", "GOV"]
    assert dropped == 3


def test_suit_01_blocks_tech_for_mei() -> None:
    found = unsuitable_lines({"TEC": 100}, FUNDS, ClientClass.C2, MATRIX)
    assert [(v.rule_id, v.subject) for v in found] == [(SUIT_01, "TEC")]


def test_suit_01_allows_a_suitable_mix() -> None:
    assert unsuitable_lines({"MMF": 40, "GOV": 60}, FUNDS, ClientClass.C2, MATRIX) == []


def conc(weights: dict[str, float], client: ClientClass = ClientClass.C3):
    return concentration_violations(
        weights,
        FUNDS,
        client,
        max_product_pct=40,
        max_equity_class_pct=60,
        exempt=[ClientClass.C5],
    )


def test_conc_01_allows_a_diversified_mix() -> None:
    assert conc({"MMF": 20, "GOV": 30, "USE": 30, "USE2": 20}) == []


def test_conc_01_blocks_one_product_over_40() -> None:
    found = conc({"MMF": 20, "GOV": 39, "USE": 41})
    assert [(v.rule_id, v.subject) for v in found] == [(CONC_01, "USE")]


def test_conc_01_blocks_one_equity_class_over_60() -> None:
    found = conc({"GOV": 35, "USE": 33, "USE2": 32}, ClientClass.C4)
    assert [(v.rule_id, v.subject, v.value_pct) for v in found] == [(CONC_01, "us_equity", 65)]


def test_conc_01_blocks_all_in_tech() -> None:
    subjects = {v.subject for v in conc({"TEC": 100}, ClientClass.C4)}
    assert subjects == {"TEC", "us_tech"}


def test_conc_01_exempts_c5() -> None:
    assert conc({"TEC": 100}, ClientClass.C5) == []


def test_fee_is_weighted_by_holding() -> None:
    assert weighted_fee_pct({"MMF": 50, "USE": 50}, FUNDS) == pytest.approx(0.07)


def test_family_split_for_the_donut() -> None:
    split = family_split({"MMF": 10, "GOV": 40, "USE": 50}, FUNDS)
    assert split == {Family.CASH: 10, Family.BONDS: 40, Family.STOCKS: 50, Family.GOLD: 0}


def test_split_amount_rounds_without_losing_a_cent() -> None:
    lines = split_amount({"A": 1, "B": 1, "C": 1}, Decimal(100))
    assert [line.amount_usd for line in lines] == [
        Decimal("33.34"),
        Decimal("33.33"),
        Decimal("33.33"),
    ]


def test_split_amount_drops_zero_weights() -> None:
    assert [line.product_id for line in split_amount({"A": 100, "B": 0}, Decimal(5))] == ["A"]


def test_split_amount_needs_positive_weights() -> None:
    with pytest.raises(ValueError, match="positive"):
        split_amount({"A": 0}, Decimal(5))


@given(
    st.dictionaries(st.sampled_from("ABCDEFG"), st.integers(1, 100), min_size=1),
    st.decimals(min_value=1, max_value=1_000_000, places=2),
)
def test_split_amount_always_sums_to_the_total(weights: dict[str, int], total: Decimal) -> None:
    lines = split_amount({k: float(v) for k, v in weights.items()}, total)
    assert sum(line.amount_usd for line in lines) == total
    assert all(line.amount_usd >= 0 for line in lines)
