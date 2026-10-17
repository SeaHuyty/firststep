import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.core.types import ClientClass
from app.engine.scoring import (
    AgeBandScore,
    HorizonBand,
    age_score,
    capacity_score,
    horizon_cap,
    risk_profile,
    tolerance_score,
)

BANDS = [AgeBandScore(30, 5), AgeBandScore(45, 4), AgeBandScore(55, 3), AgeBandScore(65, 2)]
CAPS = [HorizonBand(1, ClientClass.C1), HorizonBand(3, ClientClass.C2)]


@pytest.mark.parametrize(
    ("answers", "expected"),
    [([3, 3, 3, 3, 3], 3), ([1, 2, 2, 2, 2], 2), ([2, 3, 3, 3, 3], 3), ([2, 2, 3, 3, 3], 3)],
)
def test_tolerance_is_the_mean_rounded_half_up(answers: list[int], expected: int) -> None:
    assert tolerance_score(answers) == expected


@pytest.mark.parametrize("bad", [[], [0, 3], [6]])
def test_tolerance_rejects_out_of_range_answers(bad: list[int]) -> None:
    with pytest.raises(ValueError, match="1-5"):
        tolerance_score(bad)


@pytest.mark.parametrize(("age", "score"), [(21, 5), (30, 4), (58, 2), (64, 2)])
def test_age_bands(age: int, score: int) -> None:
    assert age_score(age, BANDS) == score


def test_age_outside_every_band_is_an_error() -> None:
    with pytest.raises(ValueError, match="no age band"):
        age_score(70, BANDS)


def test_capacity_is_the_weakest_component() -> None:
    assert capacity_score([5, 5, 5, 4]) == 4
    assert capacity_score([2, 5, 5, 2]) == 2


@pytest.mark.parametrize("bad", [[], [0], [9]])
def test_capacity_rejects_out_of_range_scores(bad: list[int]) -> None:
    with pytest.raises(ValueError, match="1-5"):
        capacity_score(bad)


@pytest.mark.parametrize(
    ("years", "cap"),
    [(0.5, ClientClass.C1), (1, ClientClass.C2), (2.9, ClientClass.C2), (3, None), (10, None)],
)
def test_hor_01_caps(years: float, cap: ClientClass | None) -> None:
    assert horizon_cap(years, CAPS) == cap


def test_leo_is_c3_limited_by_tolerance() -> None:
    profile = risk_profile(tolerance=3, capacity=4, cap=None)
    assert profile.final_class == ClientClass.C3
    assert profile.limited_by == "tolerance"


def test_mei_is_c2_limited_by_capacity_on_a_tie() -> None:
    profile = risk_profile(tolerance=2, capacity=2, cap=None)
    assert profile.final_class == ClientClass.C2
    assert profile.limited_by == "capacity"


def test_hor_01_overrides_a_higher_score() -> None:
    profile = risk_profile(tolerance=5, capacity=5, cap=ClientClass.C2)
    assert profile.final_class == ClientClass.C2
    assert profile.limited_by == "horizon"


@given(
    st.integers(1, 5),
    st.integers(1, 5),
    st.one_of(st.none(), st.sampled_from(list(ClientClass))),
)
def test_final_class_never_exceeds_any_input(
    tolerance: int, capacity: int, cap: ClientClass | None
) -> None:
    final = risk_profile(tolerance, capacity, cap).final_class
    assert final <= tolerance
    assert final <= capacity
    assert cap is None or final <= cap
